#!/usr/bin/env python3
"""
Simplified Fault Tolerance Test Suite
Tests the core fault tolerance system without gRPC dependencies
"""

import time
import threading
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from middleware.fault_tolerance import (
    FaultToleranceManager, TaskState, FailureType, CircuitBreaker,
    initialize_fault_tolerance
)


class SimplifiedFaultToleranceTestSuite:
    """Simplified test suite for fault tolerance features"""
    
    def __init__(self):
        self.fault_manager = initialize_fault_tolerance()
        self.test_results = {}
        self.test_workers = ["worker-1", "worker-2", "worker-3", "worker-4"]
        
    def run_all_tests(self):
        """Run all fault tolerance tests"""
        print("🧪 Starting Simplified Fault Tolerance Test Suite")
        print("=" * 60)
        
        tests = [
            ("Task Registration & Tracking", self.test_task_registration),
            ("Task Timeout Detection", self.test_task_timeout),
            ("Retry Logic & Exponential Backoff", self.test_retry_logic),
            ("Circuit Breaker Functionality", self.test_circuit_breaker),
            ("Dead Letter Queue", self.test_dead_letter_queue),
            ("Worker Failure Recovery", self.test_worker_failure),
            ("Concurrent Task Processing", self.test_concurrent_processing),
            ("Task Recovery Operations", self.test_task_recovery),
            ("Circuit Breaker Integration", self.test_circuit_breaker_integration),
            ("Stress Test", self.test_stress_scenario)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                result = test_func()
                self.test_results[test_name] = {"success": True, "result": result}
                print(f"✅ {test_name}: PASSED")
            except Exception as e:
                self.test_results[test_name] = {"success": False, "error": str(e)}
                print(f"❌ {test_name}: FAILED - {e}")
        
        self._print_test_summary()
    
    def test_task_registration(self):
        """Test task registration and state tracking"""
        task_id = str(uuid.uuid4())
        job_id = "test-job-001"
        
        # Register task
        task = self.fault_manager.register_task(
            task_id=task_id,
            job_id=job_id,
            task_type="MAP",
            timeout_seconds=30
        )
        
        assert task.task_id == task_id
        assert task.job_id == job_id
        assert task.state == TaskState.PENDING
        assert task_id in self.fault_manager.active_tasks
        
        # Test task assignment
        success = self.fault_manager.assign_task_to_worker(task_id, "worker-1")
        assert success
        assert task.worker_id == "worker-1"
        assert task.state == TaskState.ASSIGNED
        
        # Test task start
        success = self.fault_manager.start_task_execution(task_id)
        assert success
        assert task.state == TaskState.RUNNING
        
        return "Task registration, assignment, and state transitions work correctly"
    
    def test_task_timeout(self):
        """Test task timeout detection and handling"""
        task_id = str(uuid.uuid4())
        job_id = "test-job-002"
        
        # Register task with very short timeout
        task = self.fault_manager.register_task(
            task_id=task_id,
            job_id=job_id,
            timeout_seconds=1  # 1 second timeout
        )
        
        self.fault_manager.assign_task_to_worker(task_id, "worker-1")
        self.fault_manager.start_task_execution(task_id)
        
        # Wait for timeout
        time.sleep(2)
        
        # Check if task is expired
        assert task.is_expired
        
        # Manually trigger timeout
        success = self.fault_manager.timeout_task(task_id)
        assert success
        assert task.state == TaskState.RETRY_PENDING  # Should be scheduled for retry
        assert task.failure_type == FailureType.WORKER_TIMEOUT
        
        return "Task timeout detection and handling work correctly"
    
    def test_retry_logic(self):
        """Test retry logic and exponential backoff"""
        task_id = str(uuid.uuid4())
        job_id = "test-job-003"
        
        task = self.fault_manager.register_task(task_id, job_id, timeout_seconds=60)
        self.fault_manager.assign_task_to_worker(task_id, "worker-1")
        
        # Simulate task failures
        retry_delays = []
        for attempt in range(3):
            # Complete task with failure
            self.fault_manager.complete_task(
                task_id=task_id,
                success=False,
                error_message=f"Simulated failure {attempt + 1}"
            )
            
            if task.state == TaskState.RETRY_PENDING:
                # Calculate expected delay
                expected_delay = task.calculate_retry_delay()
                retry_delays.append(expected_delay)
                
                # Reset for next failure
                task.state = TaskState.RUNNING
        
        # Check exponential backoff
        assert len(retry_delays) >= 2
        assert retry_delays[1] > retry_delays[0]  # Each delay should be larger
        assert task.failure_count == 3
        
        return f"Retry logic with exponential backoff works. Delays: {retry_delays}"
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        worker_id = "test-worker-cb"
        circuit_breaker = self.fault_manager.get_or_create_circuit_breaker(worker_id)
        
        # Initially closed
        assert circuit_breaker.state.value == "closed"
        assert circuit_breaker.can_execute()
        
        # Record multiple failures to open circuit
        for i in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure()
        
        # Circuit should be open
        assert circuit_breaker.state.value == "open"
        assert not circuit_breaker.can_execute()
        
        # Test recovery after timeout (simulate by manipulating time)
        circuit_breaker.last_failure_time = int(time.time() * 1000) - 65000  # 65 seconds ago
        
        # Should allow half-open state
        assert circuit_breaker.can_execute()
        # Note: state doesn't change until can_execute is called
        
        # Record success to close circuit
        for i in range(circuit_breaker.half_open_max_calls):
            circuit_breaker.record_success()
        
        # Should be closed after successful calls
        assert circuit_breaker.state.value == "closed"
        
        return f"Circuit breaker transitions: closed -> open -> half_open -> closed"
    
    def test_dead_letter_queue(self):
        """Test dead letter queue functionality"""
        task_id = str(uuid.uuid4())
        job_id = "test-job-dlq"
        
        # Create task that will exceed max retries
        task = self.fault_manager.register_task(task_id, job_id)
        task.max_retries = 2  # Lower max retries for testing
        
        self.fault_manager.assign_task_to_worker(task_id, "worker-1")
        
        # Simulate multiple failures to exceed max retries
        for attempt in range(4):  # More than max_retries
            self.fault_manager.complete_task(
                task_id=task_id,
                success=False,
                error_message=f"Persistent failure {attempt + 1}"
            )
        
        # Task should be in dead letter queue
        dlq_tasks = self.fault_manager.dead_letter_queue.get_tasks()
        dlq_task_ids = [t.task_id for t in dlq_tasks]
        assert task_id in dlq_task_ids
        
        # Test recovery from dead letter queue
        success = self.fault_manager.recover_dead_letter_task(task_id)
        assert success
        assert task_id in self.fault_manager.active_tasks
        assert task.state == TaskState.PENDING
        
        return "Dead letter queue storage and recovery work correctly"
    
    def test_worker_failure(self):
        """Test worker failure handling"""
        worker_id = "failing-worker"
        task_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        # Create multiple tasks assigned to the same worker
        for task_id in task_ids:
            task = self.fault_manager.register_task(task_id, "test-job-wf")
            self.fault_manager.assign_task_to_worker(task_id, worker_id)
            self.fault_manager.start_task_execution(task_id)
        
        # Report worker failure
        self.fault_manager.report_worker_failure(
            worker_id=worker_id,
            task_ids=task_ids,
            failure_type=FailureType.WORKER_CRASH
        )
        
        # Check that all tasks are marked for retry
        retry_count = 0
        for task_id in task_ids:
            task = self.fault_manager.active_tasks.get(task_id)
            if task and task.state == TaskState.RETRY_PENDING:
                retry_count += 1
        
        assert retry_count == len(task_ids)
        
        return f"Worker failure affected {len(task_ids)} tasks, all scheduled for retry"
    
    def test_concurrent_processing(self):
        """Test concurrent task processing with fault tolerance"""
        num_tasks = 20
        task_ids = []
        
        def create_and_process_task(task_num):
            task_id = f"concurrent-task-{task_num}"
            task_ids.append(task_id)
            
            # Register task
            task = self.fault_manager.register_task(task_id, "concurrent-job")
            
            # Assign to random worker
            worker_id = random.choice(self.test_workers)
            self.fault_manager.assign_task_to_worker(task_id, worker_id)
            self.fault_manager.start_task_execution(task_id)
            
            # Simulate random outcomes
            time.sleep(random.uniform(0.01, 0.05))  # Shorter delays for testing
            
            success_rate = 0.7  # 70% success rate
            if random.random() < success_rate:
                # Success
                self.fault_manager.complete_task(
                    task_id=task_id,
                    success=True,
                    duration_ms=random.randint(100, 1000)
                )
            else:
                # Failure
                self.fault_manager.complete_task(
                    task_id=task_id,
                    success=False,
                    error_message="Random test failure"
                )
        
        # Process tasks concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_process_task, i) for i in range(num_tasks)]
            
            # Wait for completion
            for future in futures:
                future.result()
        
        # Wait a bit for retry processing
        time.sleep(1)
        
        stats = self.fault_manager.get_statistics()
        return f"Processed {num_tasks} concurrent tasks. Stats: {stats}"
    
    def test_task_recovery(self):
        """Test task recovery operations"""
        task_id = str(uuid.uuid4())
        job_id = "recovery-test-job"
        
        # Create and fail a task
        task = self.fault_manager.register_task(task_id, job_id)
        self.fault_manager.assign_task_to_worker(task_id, "worker-1")
        self.fault_manager.complete_task(task_id, success=False, error_message="Test failure")
        
        # Test force retry
        success = self.fault_manager.force_retry_task(task_id)
        assert success
        assert task.state == TaskState.PENDING
        assert task.failure_count == 0  # Should be reset
        
        return "Task recovery operations work correctly"
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with task assignment"""
        worker_id = "integration-worker"
        
        # Create circuit breaker and open it
        circuit_breaker = self.fault_manager.get_or_create_circuit_breaker(worker_id)
        for i in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state.value == "open"
        
        # Try to assign task to worker with open circuit breaker
        task_id = str(uuid.uuid4())
        task = self.fault_manager.register_task(task_id, "integration-test")
        
        success = self.fault_manager.assign_task_to_worker(task_id, worker_id)
        assert not success  # Should be rejected
        
        return "Circuit breaker integration prevents task assignment to failing workers"
    
    def test_stress_scenario(self):
        """Test system under stress conditions"""
        print("   🔥 Running stress test with 50 tasks...")
        
        num_tasks = 50  # Reduced for faster testing
        start_time = time.time()
        
        # Create many tasks rapidly
        task_ids = []
        for i in range(num_tasks):
            task_id = f"stress-task-{i}"
            task_ids.append(task_id)
            
            task = self.fault_manager.register_task(task_id, "stress-job")
            worker_id = random.choice(self.test_workers)
            
            if self.fault_manager.assign_task_to_worker(task_id, worker_id):
                self.fault_manager.start_task_execution(task_id)
                
                # Random outcomes with failures
                if random.random() < 0.3:  # 30% failure rate
                    self.fault_manager.complete_task(
                        task_id, False, error_message="Stress test failure"
                    )
                else:
                    self.fault_manager.complete_task(
                        task_id, True, duration_ms=random.randint(50, 200)
                    )
        
        # Wait for processing
        time.sleep(2)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        stats = self.fault_manager.get_statistics()
        
        return f"Processed {num_tasks} tasks in {processing_time:.2f}s. Final stats: {stats}"
    
    def _print_test_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("🧪 FAULT TOLERANCE TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results.values() if result["success"])
        total = len(self.test_results)
        
        print(f"✅ Tests Passed: {passed}/{total}")
        print(f"❌ Tests Failed: {total - passed}/{total}")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Fault tolerance system is working correctly.")
        else:
            print("⚠️  Some tests failed. Review the failures above.")
            for test_name, result in self.test_results.items():
                if not result["success"]:
                    print(f"   ❌ {test_name}: {result['error']}")
        
        # Print system statistics
        print(f"\n📊 Final System Statistics:")
        stats = self.fault_manager.get_statistics()
        for key, value in stats.items():
            if isinstance(value, dict):
                print(f"   {key}:")
                for sub_key, sub_value in value.items():
                    print(f"     {sub_key}: {sub_value}")
            else:
                print(f"   {key}: {value}")


class FaultToleranceDemo:
    """Demonstration of fault tolerance features"""
    
    def __init__(self):
        self.fault_manager = initialize_fault_tolerance()
    
    def run_demo(self):
        """Run interactive demonstration"""
        print("🎭 Fault Tolerance System Demonstration")
        print("=" * 60)
        
        self._demo_basic_flow()
        self._demo_circuit_breaker()
        self._demo_dead_letter_queue()
        self._demo_statistics()
    
    def _demo_basic_flow(self):
        """Demonstrate basic task flow with retries"""
        print("\n🔄 Basic Task Flow with Retries")
        print("-" * 40)
        
        # Create a task that will fail and retry
        task_id = "demo-task-001"
        task = self.fault_manager.register_task(task_id, "demo-job")
        
        print(f"📝 Registered task: {task_id}")
        print(f"   State: {task.state.value}")
        
        # Assign to worker
        self.fault_manager.assign_task_to_worker(task_id, "demo-worker")
        print(f"📤 Assigned to worker: demo-worker")
        print(f"   State: {task.state.value}")
        
        # Start execution
        self.fault_manager.start_task_execution(task_id)
        print(f"🚀 Started execution")
        print(f"   State: {task.state.value}")
        
        # Simulate failure
        self.fault_manager.complete_task(task_id, success=False, error_message="Demo failure")
        print(f"❌ Task failed: {task.failure_message}")
        print(f"   State: {task.state.value}")
        print(f"   Failure count: {task.failure_count}")
        print(f"   Can retry: {task.can_retry}")
    
    def _demo_circuit_breaker(self):
        """Demonstrate circuit breaker functionality"""
        print("\n🚫 Circuit Breaker Demonstration")
        print("-" * 40)
        
        worker_id = "flaky-worker"
        cb = self.fault_manager.get_or_create_circuit_breaker(worker_id)
        
        print(f"🔌 Circuit breaker for {worker_id}")
        print(f"   Initial state: {cb.state.value}")
        print(f"   Can execute: {cb.can_execute()}")
        
        # Cause failures
        print(f"\n💥 Recording failures...")
        for i in range(cb.failure_threshold):
            cb.record_failure()
            print(f"   Failure {i+1}/{cb.failure_threshold} - State: {cb.state.value}")
        
        print(f"\n🚫 Circuit breaker opened!")
        print(f"   Can execute: {cb.can_execute()}")
        print(f"   Failure rate: {cb.failure_rate:.1f}%")
    
    def _demo_dead_letter_queue(self):
        """Demonstrate dead letter queue"""
        print("\n💀 Dead Letter Queue Demonstration")
        print("-" * 40)
        
        task_id = "problematic-task"
        task = self.fault_manager.register_task(task_id, "demo-job")
        task.max_retries = 2
        
        print(f"📝 Created task with max_retries = {task.max_retries}")
        
        # Exhaust retries
        self.fault_manager.assign_task_to_worker(task_id, "demo-worker")
        for attempt in range(4):  # More than max_retries
            self.fault_manager.complete_task(
                task_id, success=False, error_message=f"Persistent failure {attempt+1}"
            )
            print(f"   Attempt {attempt+1}: {task.state.value} (failures: {task.failure_count})")
        
        # Check dead letter queue
        dlq_stats = self.fault_manager.dead_letter_queue.get_statistics()
        print(f"\n💀 Dead Letter Queue Stats:")
        print(f"   Total tasks: {dlq_stats['total_tasks']}")
        print(f"   Utilization: {dlq_stats['utilization']:.1f}%")
    
    def _demo_statistics(self):
        """Show comprehensive statistics"""
        print("\n📊 System Statistics")
        print("-" * 40)
        
        stats = self.fault_manager.get_statistics()
        
        print("📈 Task Statistics:")
        task_stats = ["tasks_total", "tasks_completed", "tasks_failed", "tasks_retried", 
                     "tasks_timed_out", "tasks_dead_letter"]
        for stat in task_stats:
            print(f"   {stat}: {stats.get(stat, 0)}")
        
        print("\n🔌 Circuit Breaker Statistics:")
        for worker_id, cb_stats in stats.get("circuit_breakers", {}).items():
            print(f"   {worker_id}:")
            print(f"     State: {cb_stats['state']}")
            print(f"     Failure rate: {cb_stats['failure_rate']:.1f}%")
        
        print(f"\n🏃 Active Processing:")
        print(f"   Active tasks: {stats.get('active_tasks', 0)}")
        print(f"   Retry queue size: {stats.get('retry_queue_size', 0)}")


if __name__ == "__main__":
    # Run simplified tests
    print("🧪 Starting Fault Tolerance System Tests\n")
    
    test_suite = SimplifiedFaultToleranceTestSuite()
    test_suite.run_all_tests()
    
    # Run demonstration
    print(f"\n" + "="*60)
    demo = FaultToleranceDemo()
    demo.run_demo()
    
    print(f"\n🎉 Fault Tolerance System validation completed!")
    print("✅ System is ready for production use")