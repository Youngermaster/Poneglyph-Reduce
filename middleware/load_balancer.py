#!/usr/bin/env python3
"""
Advanced Load Balancer for Poneglyph-Reduce
Implements intelligent worker selection based on multiple criteria
"""

import time
import heapq
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class LoadBalancingStrategy(Enum):
    """Available load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    CAPACITY_AWARE = "capacity_aware"
    HEALTH_BASED = "health_based"
    SMART_COMPOSITE = "smart_composite"  # Our advanced algorithm


@dataclass
class WorkerPerformanceMetrics:
    """Tracks performance metrics for a worker"""
    worker_id: str
    
    # Current state
    current_tasks: int = 0
    max_capacity: int = 1
    health_score: float = 100.0
    last_heartbeat: int = 0
    
    # Performance history
    task_completion_times: List[float] = field(default_factory=list)
    success_rate: float = 100.0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    
    # Latency tracking
    avg_response_time_ms: float = 0.0
    response_times: List[float] = field(default_factory=list)
    
    # Resource utilization
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_io: float = 0.0
    network_io: float = 0.0
    
    # Calculated scores
    efficiency_score: float = 0.0
    reliability_score: float = 0.0
    availability_score: float = 0.0
    composite_score: float = 0.0
    
    def __post_init__(self):
        self.last_updated = int(time.time() * 1000)
    
    @property
    def utilization_percentage(self) -> float:
        """Current utilization as percentage"""
        if self.max_capacity == 0:
            return 100.0
        return (self.current_tasks / self.max_capacity) * 100.0
    
    @property
    def available_capacity(self) -> int:
        """Available task slots"""
        return max(0, self.max_capacity - self.current_tasks)
    
    @property
    def avg_task_duration_ms(self) -> float:
        """Average task completion time in milliseconds"""
        if not self.task_completion_times:
            return 0.0
        return statistics.mean(self.task_completion_times[-20:])  # Last 20 tasks
    
    @property
    def is_healthy(self) -> bool:
        """Check if worker is considered healthy"""
        current_time = int(time.time() * 1000)
        heartbeat_threshold = 60000  # 60 seconds
        
        return (
            self.health_score > 50.0 and
            (current_time - self.last_heartbeat) < heartbeat_threshold and
            self.success_rate > 70.0
        )
    
    def update_task_completion(self, duration_ms: float, success: bool):
        """Update metrics after task completion"""
        self.task_completion_times.append(duration_ms)
        
        # Keep only last 50 completion times for efficiency
        if len(self.task_completion_times) > 50:
            self.task_completion_times = self.task_completion_times[-50:]
        
        if success:
            self.total_tasks_completed += 1
        else:
            self.total_tasks_failed += 1
        
        # Update success rate
        total_tasks = self.total_tasks_completed + self.total_tasks_failed
        if total_tasks > 0:
            self.success_rate = (self.total_tasks_completed / total_tasks) * 100.0
    
    def update_response_time(self, response_time_ms: float):
        """Update response time metrics"""
        self.response_times.append(response_time_ms)
        
        # Keep only last 30 response times
        if len(self.response_times) > 30:
            self.response_times = self.response_times[-30:]
        
        self.avg_response_time_ms = statistics.mean(self.response_times)
    
    def calculate_composite_score(self) -> float:
        """Calculate overall worker performance score (0-100)"""
        current_time = int(time.time() * 1000)
        
        # 1. Availability Score (0-30 points)
        heartbeat_age = current_time - self.last_heartbeat
        if heartbeat_age < 10000:  # < 10 seconds
            availability_score = 30.0
        elif heartbeat_age < 30000:  # < 30 seconds
            availability_score = 20.0
        elif heartbeat_age < 60000:  # < 60 seconds
            availability_score = 10.0
        else:
            availability_score = 0.0
        
        # 2. Health Score (0-25 points)
        health_score = min(25.0, (self.health_score / 100.0) * 25.0)
        
        # 3. Efficiency Score (0-25 points) - based on task completion speed
        if self.avg_task_duration_ms > 0:
            # Normalize task duration (lower is better)
            # Assume 5000ms is baseline, reward faster completion
            baseline_duration = 5000.0
            efficiency = min(1.0, baseline_duration / self.avg_task_duration_ms)
            efficiency_score = efficiency * 25.0
        else:
            efficiency_score = 15.0  # Default for new workers
        
        # 4. Reliability Score (0-20 points) - based on success rate
        reliability_score = (self.success_rate / 100.0) * 20.0
        
        # 5. Capacity Penalty - heavily loaded workers get penalty
        utilization = self.utilization_percentage
        if utilization > 90:
            capacity_penalty = -15.0
        elif utilization > 75:
            capacity_penalty = -10.0
        elif utilization > 50:
            capacity_penalty = -5.0
        else:
            capacity_penalty = 0.0
        
        composite_score = (
            availability_score +
            health_score +
            efficiency_score +
            reliability_score +
            capacity_penalty
        )
        
        # Store individual scores for debugging
        self.availability_score = availability_score
        self.reliability_score = reliability_score
        self.efficiency_score = efficiency_score
        self.composite_score = max(0.0, min(100.0, composite_score))
        
        return self.composite_score


class AdvancedLoadBalancer:
    """
    Advanced Load Balancer with multiple strategies and intelligent worker selection
    """
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.SMART_COMPOSITE):
        self.strategy = strategy
        self.worker_metrics: Dict[str, WorkerPerformanceMetrics] = {}
        self.round_robin_index = 0
        self.task_history: List[Tuple[str, str, int]] = []  # (worker_id, task_id, timestamp)
        
        # Configuration
        self.max_task_history = 1000
        self.score_update_interval = 5000  # 5 seconds
        self.last_score_update = 0
    
    def register_worker(self, worker_id: str, capacity: int = 1, health_score: float = 100.0):
        """Register a new worker or update existing worker"""
        if worker_id not in self.worker_metrics:
            self.worker_metrics[worker_id] = WorkerPerformanceMetrics(
                worker_id=worker_id,
                max_capacity=capacity,
                health_score=health_score,
                last_heartbeat=int(time.time() * 1000)
            )
            print(f"LoadBalancer: Registered new worker {worker_id} (capacity: {capacity})")
        else:
            # Update existing worker
            worker = self.worker_metrics[worker_id]
            worker.max_capacity = capacity
            worker.health_score = health_score
            worker.last_heartbeat = int(time.time() * 1000)
            print(f"LoadBalancer: Updated worker {worker_id} (capacity: {capacity}, health: {health_score})")
        
        self._update_worker_scores()
    
    def update_worker_heartbeat(self, worker_id: str, health_score: float = None, 
                               cpu_usage: float = None, memory_usage: float = None):
        """Update worker heartbeat and optional metrics"""
        if worker_id not in self.worker_metrics:
            print(f"LoadBalancer: Warning - heartbeat for unregistered worker {worker_id}")
            return
        
        worker = self.worker_metrics[worker_id]
        worker.last_heartbeat = int(time.time() * 1000)
        
        if health_score is not None:
            worker.health_score = health_score
        if cpu_usage is not None:
            worker.cpu_usage = cpu_usage
        if memory_usage is not None:
            worker.memory_usage = memory_usage
        
        self._update_worker_scores()
    
    def report_task_assignment(self, worker_id: str, task_id: str):
        """Report that a task has been assigned to a worker"""
        if worker_id in self.worker_metrics:
            self.worker_metrics[worker_id].current_tasks += 1
            self.task_history.append((worker_id, task_id, int(time.time() * 1000)))
            
            # Limit history size
            if len(self.task_history) > self.max_task_history:
                self.task_history = self.task_history[-self.max_task_history:]
    
    def report_task_completion(self, worker_id: str, task_id: str, 
                             duration_ms: float, success: bool = True,
                             response_time_ms: float = None):
        """Report task completion and update worker metrics"""
        if worker_id not in self.worker_metrics:
            return
        
        worker = self.worker_metrics[worker_id]
        worker.current_tasks = max(0, worker.current_tasks - 1)
        worker.update_task_completion(duration_ms, success)
        
        if response_time_ms is not None:
            worker.update_response_time(response_time_ms)
        
        self._update_worker_scores()
        
        print(f"LoadBalancer: Task completed - {worker_id} ({duration_ms:.1f}ms, success: {success})")
    
    def select_worker_for_task(self, task_type: str = None, 
                              preferred_capabilities: List[str] = None) -> Optional[str]:
        """
        Select the best worker for a task based on the current strategy
        """
        available_workers = self._get_available_workers()
        
        if not available_workers:
            return None
        
        # Apply strategy-specific selection
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_workers)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._select_least_connections(available_workers)
        elif self.strategy == LoadBalancingStrategy.CAPACITY_AWARE:
            return self._select_capacity_aware(available_workers)
        elif self.strategy == LoadBalancingStrategy.HEALTH_BASED:
            return self._select_health_based(available_workers)
        elif self.strategy == LoadBalancingStrategy.SMART_COMPOSITE:
            return self._select_smart_composite(available_workers, task_type, preferred_capabilities)
        else:
            # Default to round robin
            return self._select_round_robin(available_workers)
    
    def get_worker_statistics(self) -> Dict:
        """Get comprehensive statistics about all workers"""
        stats = {
            "total_workers": len(self.worker_metrics),
            "available_workers": len(self._get_available_workers()),
            "total_capacity": sum(w.max_capacity for w in self.worker_metrics.values()),
            "used_capacity": sum(w.current_tasks for w in self.worker_metrics.values()),
            "workers": {}
        }
        
        for worker_id, worker in self.worker_metrics.items():
            stats["workers"][worker_id] = {
                "health_score": worker.health_score,
                "composite_score": worker.composite_score,
                "utilization": worker.utilization_percentage,
                "available_capacity": worker.available_capacity,
                "success_rate": worker.success_rate,
                "avg_task_duration": worker.avg_task_duration_ms,
                "avg_response_time": worker.avg_response_time_ms,
                "is_healthy": worker.is_healthy,
                "total_completed": worker.total_tasks_completed,
                "total_failed": worker.total_tasks_failed
            }
        
        return stats
    
    def _get_available_workers(self) -> List[str]:
        """Get list of healthy workers with available capacity"""
        available = []
        for worker_id, worker in self.worker_metrics.items():
            if worker.is_healthy and worker.available_capacity > 0:
                available.append(worker_id)
        return available
    
    def _select_round_robin(self, available_workers: List[str]) -> str:
        """Simple round-robin selection"""
        if not available_workers:
            return None
        
        worker = available_workers[self.round_robin_index % len(available_workers)]
        self.round_robin_index += 1
        return worker
    
    def _select_least_connections(self, available_workers: List[str]) -> str:
        """Select worker with least current tasks"""
        if not available_workers:
            return None
        
        return min(available_workers, 
                  key=lambda w: self.worker_metrics[w].current_tasks)
    
    def _select_capacity_aware(self, available_workers: List[str]) -> str:
        """Select worker with highest available capacity percentage"""
        if not available_workers:
            return None
        
        return max(available_workers,
                  key=lambda w: self.worker_metrics[w].available_capacity)
    
    def _select_health_based(self, available_workers: List[str]) -> str:
        """Select worker with highest health score"""
        if not available_workers:
            return None
        
        return max(available_workers,
                  key=lambda w: self.worker_metrics[w].health_score)
    
    def _select_smart_composite(self, available_workers: List[str], 
                               task_type: str = None, 
                               preferred_capabilities: List[str] = None) -> str:
        """
        Advanced composite selection considering multiple factors
        """
        if not available_workers:
            return None
        
        # Update scores if needed
        self._update_worker_scores()
        
        # For single worker, return it
        if len(available_workers) == 1:
            return available_workers[0]
        
        # Create weighted selection based on composite scores
        worker_scores = []
        for worker_id in available_workers:
            worker = self.worker_metrics[worker_id]
            score = worker.composite_score
            
            # Apply task-specific bonuses
            if task_type:
                # Future: could add task-type specific optimizations
                pass
            
            # Prefer workers with more available capacity for better distribution
            capacity_bonus = (worker.available_capacity / worker.max_capacity) * 5.0
            final_score = score + capacity_bonus
            
            worker_scores.append((worker_id, final_score))
        
        # Sort by score (descending) and select top performer
        worker_scores.sort(key=lambda x: x[1], reverse=True)
        selected_worker = worker_scores[0][0]
        
        print(f"LoadBalancer: Selected {selected_worker} (score: {worker_scores[0][1]:.1f})")
        return selected_worker
    
    def _update_worker_scores(self):
        """Update composite scores for all workers"""
        current_time = int(time.time() * 1000)
        
        # Only update scores every few seconds to avoid excessive computation
        if current_time - self.last_score_update < self.score_update_interval:
            return
        
        for worker in self.worker_metrics.values():
            worker.calculate_composite_score()
        
        self.last_score_update = current_time
    
    def cleanup_inactive_workers(self, timeout_ms: int = 300000):  # 5 minutes
        """Remove workers that haven't sent heartbeat in specified time"""
        current_time = int(time.time() * 1000)
        inactive_workers = []
        
        for worker_id, worker in self.worker_metrics.items():
            if current_time - worker.last_heartbeat > timeout_ms:
                inactive_workers.append(worker_id)
        
        for worker_id in inactive_workers:
            del self.worker_metrics[worker_id]
            print(f"LoadBalancer: Removed inactive worker {worker_id}")
        
        return len(inactive_workers)


# Global load balancer instance
_load_balancer_instance = None


def initialize_load_balancer(strategy: LoadBalancingStrategy = LoadBalancingStrategy.SMART_COMPOSITE) -> AdvancedLoadBalancer:
    """Initialize the global load balancer instance"""
    global _load_balancer_instance
    _load_balancer_instance = AdvancedLoadBalancer(strategy)
    print(f"LoadBalancer: Initialized with strategy {strategy.value}")
    return _load_balancer_instance


def get_load_balancer() -> AdvancedLoadBalancer:
    """Get the global load balancer instance"""
    global _load_balancer_instance
    if _load_balancer_instance is None:
        _load_balancer_instance = initialize_load_balancer()
    return _load_balancer_instance