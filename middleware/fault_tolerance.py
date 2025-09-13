#!/usr/bin/env python3
"""
Fault Tolerance & Recovery System for Poneglyph-Reduce
Implements comprehensive failure handling, retry logic, and recovery mechanisms
"""

import time
import threading
import json
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import heapq
import uuid
from collections import defaultdict, deque


class TaskState(Enum):
    """Task execution states"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    DEAD_LETTER = "dead_letter"
    ABANDONED = "abandoned"


class FailureType(Enum):
    """Types of failures that can occur"""
    WORKER_TIMEOUT = "worker_timeout"
    WORKER_CRASH = "worker_crash"
    TASK_EXECUTION_ERROR = "task_execution_error"
    NETWORK_ERROR = "network_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class TaskExecution:
    """Represents a task execution attempt"""
    task_id: str
    job_id: str
    worker_id: Optional[str] = None
    attempt_number: int = 1
    assigned_at: int = 0
    started_at: int = 0
    completed_at: int = 0
    state: TaskState = TaskState.PENDING
    
    # Task details
    task_type: str = "MAP"
    payload: Any = None
    script_url: str = ""
    capabilities: List[str] = field(default_factory=list)
    
    # Failure tracking
    failure_type: Optional[FailureType] = None
    failure_message: str = ""
    failure_count: int = 0
    last_failure_time: int = 0
    
    # Timing and performance
    timeout_seconds: int = 300  # 5 minutes default
    expected_duration_ms: int = 5000  # 5 seconds default
    actual_duration_ms: int = 0
    
    # Recovery metadata
    retry_after: int = 0
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    
    def __post_init__(self):
        if self.assigned_at == 0:
            self.assigned_at = int(time.time() * 1000)
    
    @property
    def is_expired(self) -> bool:
        """Check if task has exceeded timeout"""
        if self.state not in [TaskState.ASSIGNED, TaskState.RUNNING]:
            return False
        
        current_time = int(time.time() * 1000)
        timeout_ms = self.timeout_seconds * 1000
        
        if self.started_at > 0:
            return (current_time - self.started_at) > timeout_ms
        else:
            return (current_time - self.assigned_at) > timeout_ms
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return (
            self.failure_count < self.max_retries and
            self.state in [TaskState.FAILED, TaskState.RETRY_PENDING] and
            int(time.time() * 1000) >= self.retry_after
        )
    
    def calculate_retry_delay(self) -> int:
        """Calculate exponential backoff delay"""
        base_delay = 1000  # 1 second
        delay = base_delay * (self.backoff_multiplier ** self.failure_count)
        # Add jitter (±20%)
        import random
        jitter = random.uniform(0.8, 1.2)
        return int(delay * jitter)


@dataclass
class CircuitBreaker:
    """Circuit breaker for worker fault tolerance"""
    worker_id: str
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    half_open_max_calls: int = 3
    
    # State tracking
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: int = 0
    last_success_time: int = 0
    half_open_calls: int = 0
    
    # Statistics
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    
    def record_success(self):
        """Record successful call"""
        current_time = int(time.time() * 1000)
        self.total_calls += 1
        self.total_successes += 1
        self.last_success_time = current_time
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Service recovered, close circuit
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.half_open_calls = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed call"""
        current_time = int(time.time() * 1000)
        self.total_calls += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = current_time
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                # Open circuit
                self.state = CircuitBreakerState.OPEN
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Failed during test, keep circuit open
            self.state = CircuitBreakerState.OPEN
            self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """Check if calls are allowed through circuit"""
        current_time = int(time.time() * 1000)
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (current_time - self.last_failure_time) > (self.recovery_timeout_seconds * 1000):
                # Try half-open state
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        
        return False
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage"""
        if self.total_calls == 0:
            return 0.0
        return (self.total_failures / self.total_calls) * 100


class DeadLetterQueue:
    """Queue for tasks that cannot be processed"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.tasks: deque = deque(maxlen=max_size)
        self.task_reasons: Dict[str, str] = {}
        self.lock = threading.Lock()
    
    def add_task(self, task: TaskExecution, reason: str):
        """Add task to dead letter queue"""
        with self.lock:
            task.state = TaskState.DEAD_LETTER
            self.tasks.append(task)
            self.task_reasons[task.task_id] = reason
            
            print(f"💀 Dead Letter: Task {task.task_id} - {reason}")
    
    def get_tasks(self, limit: int = None) -> List[TaskExecution]:
        """Get tasks from dead letter queue"""
        with self.lock:
            if limit is None:
                return list(self.tasks)
            else:
                return list(self.tasks)[:limit]
    
    def remove_task(self, task_id: str) -> bool:
        """Remove task from dead letter queue"""
        with self.lock:
            for i, task in enumerate(self.tasks):
                if task.task_id == task_id:
                    del self.tasks[i]
                    self.task_reasons.pop(task_id, None)
                    return True
            return False
    
    def get_statistics(self) -> Dict:
        """Get dead letter queue statistics"""
        with self.lock:
            reasons = defaultdict(int)
            for reason in self.task_reasons.values():
                reasons[reason] += 1
            
            return {
                "total_tasks": len(self.tasks),
                "max_size": self.max_size,
                "utilization": (len(self.tasks) / self.max_size) * 100,
                "failure_reasons": dict(reasons)
            }


class FaultToleranceManager:
    """Main fault tolerance and recovery system"""
    
    def __init__(self):
        # Task tracking
        self.active_tasks: Dict[str, TaskExecution] = {}
        self.retry_queue: List[TaskExecution] = []  # Heap queue for retries
        self.completed_tasks: Dict[str, TaskExecution] = {}
        
        # Circuit breakers per worker
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Dead letter queue
        self.dead_letter_queue = DeadLetterQueue()
        
        # Configuration
        self.default_timeout_seconds = 300  # 5 minutes
        self.max_retries = 3
        self.retry_check_interval = 5  # Check every 5 seconds
        self.timeout_check_interval = 10  # Check every 10 seconds
        self.circuit_breaker_enabled = True
        
        # Background threads
        self.retry_thread = None
        self.timeout_thread = None
        self.is_running = False
        
        # Statistics
        self.stats = {
            "tasks_total": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "tasks_timed_out": 0,
            "tasks_dead_letter": 0,
            "workers_circuit_opened": 0,
            "recovery_attempts": 0
        }
        
        # Callbacks
        self.on_task_retry: Optional[Callable] = None
        self.on_task_timeout: Optional[Callable] = None
        self.on_task_dead_letter: Optional[Callable] = None
        self.on_circuit_breaker_opened: Optional[Callable] = None
    
    def start(self):
        """Start fault tolerance background processes"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start retry processing thread
        self.retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.start()
        
        # Start timeout monitoring thread
        self.timeout_thread = threading.Thread(target=self._timeout_loop, daemon=True)
        self.timeout_thread.start()
        
        print("🛡️ Fault Tolerance Manager started")
    
    def stop(self):
        """Stop fault tolerance system"""
        self.is_running = False
        print("🛡️ Fault Tolerance Manager stopped")
    
    def register_task(self, task_id: str, job_id: str, worker_id: str = None, 
                     task_type: str = "MAP", timeout_seconds: int = None) -> TaskExecution:
        """Register a new task for monitoring"""
        task = TaskExecution(
            task_id=task_id,
            job_id=job_id,
            worker_id=worker_id,
            task_type=task_type,
            timeout_seconds=timeout_seconds or self.default_timeout_seconds
        )
        
        self.active_tasks[task_id] = task
        self.stats["tasks_total"] += 1
        
        return task
    
    def assign_task_to_worker(self, task_id: str, worker_id: str) -> bool:
        """Assign task to worker with circuit breaker check"""
        task = self.active_tasks.get(task_id)
        if not task:
            return False
        
        # Check circuit breaker
        if self.circuit_breaker_enabled:
            circuit_breaker = self.get_or_create_circuit_breaker(worker_id)
            if not circuit_breaker.can_execute():
                print(f"🚫 Circuit breaker OPEN for worker {worker_id}, rejecting task {task_id}")
                return False
        
        # Assign task
        task.worker_id = worker_id
        task.state = TaskState.ASSIGNED
        task.assigned_at = int(time.time() * 1000)
        
        print(f"📤 Task {task_id} assigned to worker {worker_id}")
        return True
    
    def start_task_execution(self, task_id: str) -> bool:
        """Mark task as started"""
        task = self.active_tasks.get(task_id)
        if not task:
            return False
        
        task.state = TaskState.RUNNING
        task.started_at = int(time.time() * 1000)
        
        return True
    
    def complete_task(self, task_id: str, success: bool, duration_ms: int = 0, 
                     error_message: str = "") -> bool:
        """Complete task execution"""
        task = self.active_tasks.get(task_id)
        if not task:
            return False
        
        current_time = int(time.time() * 1000)
        task.completed_at = current_time
        task.actual_duration_ms = duration_ms
        
        if success:
            task.state = TaskState.COMPLETED
            self.stats["tasks_completed"] += 1
            
            # Record success in circuit breaker
            if task.worker_id and self.circuit_breaker_enabled:
                circuit_breaker = self.get_or_create_circuit_breaker(task.worker_id)
                circuit_breaker.record_success()
            
            print(f"✅ Task {task_id} completed successfully ({duration_ms}ms)")
        else:
            self._handle_task_failure(task, FailureType.TASK_EXECUTION_ERROR, error_message)
        
        # Move to completed tasks
        self.completed_tasks[task_id] = self.active_tasks.pop(task_id)
        
        return True
    
    def _handle_task_failure(self, task: TaskExecution, failure_type: FailureType, 
                           error_message: str = ""):
        """Handle task failure with retry logic"""
        current_time = int(time.time() * 1000)
        
        task.failure_type = failure_type
        task.failure_message = error_message
        task.failure_count += 1
        task.last_failure_time = current_time
        task.state = TaskState.FAILED
        
        self.stats["tasks_failed"] += 1
        
        # Record failure in circuit breaker
        if task.worker_id and self.circuit_breaker_enabled:
            circuit_breaker = self.get_or_create_circuit_breaker(task.worker_id)
            circuit_breaker.record_failure()
            
            if circuit_breaker.state == CircuitBreakerState.OPEN:
                self.stats["workers_circuit_opened"] += 1
                if self.on_circuit_breaker_opened:
                    self.on_circuit_breaker_opened(task.worker_id, circuit_breaker)
        
        # Check if task can be retried
        if task.can_retry:
            retry_delay = task.calculate_retry_delay()
            task.retry_after = current_time + retry_delay
            task.state = TaskState.RETRY_PENDING
            task.worker_id = None  # Clear worker assignment for retry
            
            # Add to retry queue
            heapq.heappush(self.retry_queue, (task.retry_after, task.task_id))
            
            self.stats["tasks_retried"] += 1
            
            print(f"🔄 Task {task.task_id} scheduled for retry {task.failure_count}/{task.max_retries} "
                  f"in {retry_delay}ms (reason: {failure_type.value})")
            
            if self.on_task_retry:
                self.on_task_retry(task, failure_type, error_message)
        else:
            # Send to dead letter queue
            reason = f"Max retries exceeded ({task.max_retries}) - {failure_type.value}: {error_message}"
            self.dead_letter_queue.add_task(task, reason)
            self.stats["tasks_dead_letter"] += 1
            
            if self.on_task_dead_letter:
                self.on_task_dead_letter(task, reason)
    
    def timeout_task(self, task_id: str) -> bool:
        """Mark task as timed out"""
        task = self.active_tasks.get(task_id)
        if not task:
            return False
        
        print(f"⏰ Task {task_id} timed out (assigned to {task.worker_id})")
        
        self.stats["tasks_timed_out"] += 1
        self._handle_task_failure(task, FailureType.WORKER_TIMEOUT, 
                                f"Task exceeded {task.timeout_seconds}s timeout")
        
        if self.on_task_timeout:
            self.on_task_timeout(task)
        
        return True
    
    def report_worker_failure(self, worker_id: str, task_ids: List[str], 
                            failure_type: FailureType = FailureType.WORKER_CRASH):
        """Report worker failure affecting multiple tasks"""
        print(f"💥 Worker {worker_id} failed, affecting {len(task_ids)} tasks")
        
        for task_id in task_ids:
            task = self.active_tasks.get(task_id)
            if task and task.worker_id == worker_id:
                self._handle_task_failure(task, failure_type, f"Worker {worker_id} failed")
    
    def get_or_create_circuit_breaker(self, worker_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for worker"""
        if worker_id not in self.circuit_breakers:
            self.circuit_breakers[worker_id] = CircuitBreaker(worker_id=worker_id)
        return self.circuit_breakers[worker_id]
    
    def _retry_loop(self):
        """Background thread for processing retry queue"""
        while self.is_running:
            try:
                current_time = int(time.time() * 1000)
                
                # Process ready retries
                while self.retry_queue and self.retry_queue[0][0] <= current_time:
                    retry_time, task_id = heapq.heappop(self.retry_queue)
                    
                    task = self.active_tasks.get(task_id)
                    if task and task.state == TaskState.RETRY_PENDING:
                        task.state = TaskState.PENDING
                        task.attempt_number += 1
                        
                        print(f"🔄 Retrying task {task_id} (attempt {task.attempt_number})")
                        
                        if self.on_task_retry:
                            self.on_task_retry(task, task.failure_type, task.failure_message)
                
                time.sleep(self.retry_check_interval)
                
            except Exception as e:
                print(f"❌ Retry loop error: {e}")
                time.sleep(1)
    
    def _timeout_loop(self):
        """Background thread for monitoring task timeouts"""
        while self.is_running:
            try:
                current_time = int(time.time() * 1000)
                timed_out_tasks = []
                
                # Check for timed out tasks
                for task_id, task in self.active_tasks.items():
                    if task.is_expired:
                        timed_out_tasks.append(task_id)
                
                # Process timeouts
                for task_id in timed_out_tasks:
                    self.timeout_task(task_id)
                
                time.sleep(self.timeout_check_interval)
                
            except Exception as e:
                print(f"❌ Timeout loop error: {e}")
                time.sleep(1)
    
    def get_statistics(self) -> Dict:
        """Get comprehensive fault tolerance statistics"""
        stats = self.stats.copy()
        
        # Add circuit breaker stats
        circuit_stats = {}
        for worker_id, cb in self.circuit_breakers.items():
            circuit_stats[worker_id] = {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "failure_rate": cb.failure_rate,
                "total_calls": cb.total_calls,
                "total_successes": cb.total_successes,
                "total_failures": cb.total_failures
            }
        
        stats["circuit_breakers"] = circuit_stats
        stats["dead_letter_queue"] = self.dead_letter_queue.get_statistics()
        stats["active_tasks"] = len(self.active_tasks)
        stats["retry_queue_size"] = len(self.retry_queue)
        
        return stats
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get detailed status of a specific task"""
        # Check active tasks
        task = self.active_tasks.get(task_id)
        if not task:
            # Check completed tasks
            task = self.completed_tasks.get(task_id)
        
        if not task:
            return None
        
        return {
            "task_id": task.task_id,
            "job_id": task.job_id,
            "worker_id": task.worker_id,
            "state": task.state.value,
            "attempt_number": task.attempt_number,
            "failure_count": task.failure_count,
            "assigned_at": task.assigned_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "timeout_seconds": task.timeout_seconds,
            "actual_duration_ms": task.actual_duration_ms,
            "failure_type": task.failure_type.value if task.failure_type else None,
            "failure_message": task.failure_message,
            "can_retry": task.can_retry,
            "is_expired": task.is_expired
        }
    
    def force_retry_task(self, task_id: str) -> bool:
        """Force retry a task (admin operation)"""
        task = self.active_tasks.get(task_id) or self.completed_tasks.get(task_id)
        if not task:
            return False
        
        if task.task_id in self.completed_tasks:
            # Move back to active tasks
            self.active_tasks[task_id] = self.completed_tasks.pop(task_id)
        
        task.state = TaskState.PENDING
        task.worker_id = None
        task.failure_count = 0
        task.retry_after = 0
        
        print(f"🔧 Force retrying task {task_id}")
        return True
    
    def recover_dead_letter_task(self, task_id: str) -> bool:
        """Recover task from dead letter queue"""
        tasks = self.dead_letter_queue.get_tasks()
        
        for task in tasks:
            if task.task_id == task_id:
                # Remove from dead letter queue
                self.dead_letter_queue.remove_task(task_id)
                
                # Reset task for retry
                task.state = TaskState.PENDING
                task.worker_id = None
                task.failure_count = 0
                task.retry_after = 0
                
                # Add back to active tasks
                self.active_tasks[task_id] = task
                
                print(f"♻️ Recovered task {task_id} from dead letter queue")
                return True
        
        return False


# Global fault tolerance manager instance
_fault_tolerance_manager = None


def initialize_fault_tolerance() -> FaultToleranceManager:
    """Initialize the global fault tolerance manager"""
    global _fault_tolerance_manager
    _fault_tolerance_manager = FaultToleranceManager()
    _fault_tolerance_manager.start()
    return _fault_tolerance_manager


def get_fault_tolerance_manager() -> FaultToleranceManager:
    """Get the global fault tolerance manager instance"""
    global _fault_tolerance_manager
    if _fault_tolerance_manager is None:
        _fault_tolerance_manager = initialize_fault_tolerance()
    return _fault_tolerance_manager