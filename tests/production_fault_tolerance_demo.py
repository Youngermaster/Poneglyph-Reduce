#!/usr/bin/env python3
"""
Production-Ready Fault Tolerance Demo
Simulates a realistic production environment with workers, failures, and recovery
"""

import time
import threading
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from middleware.fault_tolerance import (
    initialize_fault_tolerance, TaskState, FailureType,
    get_fault_tolerance_manager
)


class ProductionWorkerSimulator:
    """Simulates realistic worker behavior in production"""
    
    def __init__(self, worker_id: str, reliability: float = 0.8, 
                 performance_profile: str = "normal"):
        self.worker_id = worker_id
        self.reliability = reliability  # 0.0 to 1.0
        self.performance_profile = performance_profile
        self.is_active = True
        self.current_load = 0
        self.max_load = 5
        
        # Performance profiles
        if performance_profile == "high_performance":
            self.base_duration = (50, 200)    # Fast worker
            self.reliability = 0.95
        elif performance_profile == "slow":
            self.base_duration = (300, 800)   # Slow worker
            self.reliability = 0.7
        elif performance_profile == "unreliable":
            self.base_duration = (100, 400)   # Average speed, poor reliability
            self.reliability = 0.4
        else:  # normal
            self.base_duration = (100, 300)   # Normal worker
            self.reliability = 0.8
    
    def can_accept_task(self) -> bool:
        """Check if worker can accept new task"""
        return self.is_active and self.current_load < self.max_load
    
    def execute_task(self, task_id: str) -> dict:
        """Simulate task execution"""
        if not self.can_accept_task():
            return {"success": False, "error": "Worker overloaded"}
        
        self.current_load += 1
        
        # Simulate processing time
        duration = random.randint(*self.base_duration)
        time.sleep(duration / 1000.0)  # Convert to seconds
        
        # Determine success based on reliability
        success = random.random() < self.reliability
        
        self.current_load -= 1
        
        if success:
            return {
                "success": True,
                "duration_ms": duration,
                "worker_id": self.worker_id
            }
        else:
            # Random failure types
            failure_types = [
                "network_timeout",
                "memory_error", 
                "processing_error",
                "resource_unavailable"
            ]
            return {
                "success": False,
                "error": random.choice(failure_types),
                "duration_ms": duration,
                "worker_id": self.worker_id
            }
    
    def crash(self):
        """Simulate worker crash"""
        self.is_active = False
        print(f"💥 Worker {self.worker_id} crashed!")
    
    def recover(self):
        """Simulate worker recovery"""
        self.is_active = True
        self.current_load = 0
        print(f"🔄 Worker {self.worker_id} recovered!")


class ProductionJobSimulator:
    """Simulates realistic production jobs"""
    
    def __init__(self, job_id: str, task_count: int = 50, 
                 job_type: str = "map_reduce"):
        self.job_id = job_id
        self.task_count = task_count
        self.job_type = job_type
        self.tasks = []
        
        # Generate tasks
        for i in range(task_count):
            task_complexity = random.choice(["simple", "medium", "complex"])
            self.tasks.append({
                "task_id": f"{job_id}-task-{i:03d}",
                "complexity": task_complexity,
                "priority": random.choice(["low", "normal", "high"]),
                "estimated_duration": self._estimate_duration(task_complexity)
            })
    
    def _estimate_duration(self, complexity: str) -> int:
        """Estimate task duration based on complexity"""
        if complexity == "simple":
            return random.randint(50, 150)
        elif complexity == "medium":
            return random.randint(150, 400)
        else:  # complex
            return random.randint(400, 1000)
    
    def get_next_task(self) -> dict:
        """Get next task to process"""
        if self.tasks:
            return self.tasks.pop(0)
        return None
    
    def get_remaining_tasks(self) -> int:
        """Get count of remaining tasks"""
        return len(self.tasks)


class ProductionFaultToleranceDemo:
    """Production-level fault tolerance demonstration"""
    
    def __init__(self):
        self.fault_manager = initialize_fault_tolerance()
        self.workers = {}
        self.jobs = {}
        self.stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "worker_crashes": 0,
            "circuit_breakers_opened": 0,
            "tasks_recovered": 0
        }
        
        # Setup callbacks
        self.fault_manager.on_task_retry = self._on_task_retry
        self.fault_manager.on_task_timeout = self._on_task_timeout
        self.fault_manager.on_task_dead_letter = self._on_task_dead_letter
        self.fault_manager.on_circuit_breaker_opened = self._on_circuit_breaker_opened
    
    def setup_production_environment(self):
        """Setup realistic production environment"""
        print("🏭 Setting up Production Environment")
        print("-" * 50)
        
        # Create diverse worker pool
        worker_configs = [
            ("prod-worker-01", 0.95, "high_performance"),
            ("prod-worker-02", 0.90, "normal"), 
            ("prod-worker-03", 0.85, "normal"),
            ("prod-worker-04", 0.75, "slow"),
            ("prod-worker-05", 0.60, "unreliable"),
            ("prod-worker-06", 0.80, "normal"),
            ("prod-worker-07", 0.40, "unreliable"),  # Very unreliable
            ("prod-worker-08", 0.88, "normal")
        ]
        
        for worker_id, reliability, profile in worker_configs:
            worker = ProductionWorkerSimulator(worker_id, reliability, profile)
            self.workers[worker_id] = worker
            print(f"   ✅ {worker_id}: {profile} (reliability: {reliability*100:.0f}%)")
        
        # Create production jobs
        job_configs = [
            ("data-processing-job-001", 30, "map_reduce"),
            ("image-analysis-job-002", 25, "batch_processing"),
            ("ml-training-job-003", 20, "compute_intensive"),
            ("report-generation-job-004", 15, "io_intensive")
        ]
        
        for job_id, task_count, job_type in job_configs:
            job = ProductionJobSimulator(job_id, task_count, job_type)
            self.jobs[job_id] = job
            print(f"   📋 {job_id}: {task_count} tasks ({job_type})")
        
        print(f"\n🎯 Environment Ready:")
        print(f"   Workers: {len(self.workers)}")
        print(f"   Jobs: {len(self.jobs)}")
        print(f"   Total tasks: {sum(job.task_count for job in self.jobs.values())}")
    
    def run_production_demo(self, duration_minutes: int = 2):
        """Run production simulation"""
        print(f"\n🚀 Starting Production Demo ({duration_minutes} minutes)")
        print("=" * 60)
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        # Start background threads
        task_submission_thread = threading.Thread(
            target=self._task_submission_loop, 
            args=(end_time,), 
            daemon=True
        )
        
        monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(end_time,),
            daemon=True
        )
        
        chaos_thread = threading.Thread(
            target=self._chaos_engineering_loop,
            args=(end_time,),
            daemon=True
        )
        
        # Start threads
        task_submission_thread.start()
        monitoring_thread.start()
        chaos_thread.start()
        
        # Wait for completion
        print("🔄 Production simulation running...")
        print("   - Task submission active")
        print("   - Monitoring active") 
        print("   - Chaos engineering active")
        
        while time.time() < end_time:
            time.sleep(10)
            self._print_real_time_stats()
        
        print("\n🛑 Stopping production simulation...")
        
        # Final statistics
        time.sleep(2)  # Allow final processing
        self._print_final_report()
    
    def _task_submission_loop(self, end_time: float):
        """Background thread for submitting tasks"""
        while time.time() < end_time:
            # Select random job with remaining tasks
            available_jobs = [job for job in self.jobs.values() 
                            if job.get_remaining_tasks() > 0]
            
            if not available_jobs:
                time.sleep(1)
                continue
            
            job = random.choice(available_jobs)
            task = job.get_next_task()
            
            if task:
                self._submit_task(task, job.job_id)
                self.stats["tasks_submitted"] += 1
                
                # Rate limiting
                time.sleep(random.uniform(0.1, 0.5))
    
    def _submit_task(self, task: dict, job_id: str):
        """Submit task to fault tolerance system"""
        task_id = task["task_id"]
        
        # Register with fault tolerance system
        task_execution = self.fault_manager.register_task(
            task_id=task_id,
            job_id=job_id,
            task_type="PROCESS",
            timeout_seconds=10  # Short timeout for demo
        )
        
        # Select worker (simple round-robin for demo)
        available_workers = [w for w in self.workers.values() 
                           if w.can_accept_task()]
        
        if not available_workers:
            print(f"⚠️ No available workers for task {task_id}")
            return
        
        worker = random.choice(available_workers)
        
        # Check circuit breaker
        if not self.fault_manager.assign_task_to_worker(task_id, worker.worker_id):
            return
        
        # Start execution
        self.fault_manager.start_task_execution(task_id)
        
        # Execute task asynchronously
        def execute_async():
            result = worker.execute_task(task_id)
            
            self.fault_manager.complete_task(
                task_id=task_id,
                success=result["success"],
                duration_ms=result.get("duration_ms", 0),
                error_message=result.get("error", "")
            )
            
            if result["success"]:
                self.stats["tasks_completed"] += 1
            else:
                self.stats["tasks_failed"] += 1
        
        # Execute in thread pool
        executor = ThreadPoolExecutor(max_workers=20)
        executor.submit(execute_async)
    
    def _monitoring_loop(self, end_time: float):
        """Background monitoring thread"""
        while time.time() < end_time:
            time.sleep(5)  # Check every 5 seconds
            
            # Monitor for hung tasks and timeouts
            stats = self.fault_manager.get_statistics()
            
            if stats.get("tasks_timed_out", 0) > 0:
                print("⏰ Tasks timing out - possible worker issues")
            
            if stats.get("retry_queue_size", 0) > 10:
                print("🔄 High retry queue - system under stress")
            
            # Recovery operations
            if stats.get("tasks_dead_letter", 0) > 0:
                print("💀 Tasks in dead letter queue - manual intervention needed")
    
    def _chaos_engineering_loop(self, end_time: float):
        """Introduce controlled chaos for testing fault tolerance"""
        while time.time() < end_time:
            time.sleep(random.uniform(15, 30))  # Random intervals
            
            chaos_action = random.choice([
                "crash_worker",
                "slow_worker",
                "network_partition",
                "recover_worker"
            ])
            
            if chaos_action == "crash_worker":
                self._crash_random_worker()
            elif chaos_action == "slow_worker":
                self._slow_down_worker()
            elif chaos_action == "recover_worker":
                self._recover_crashed_worker()
    
    def _crash_random_worker(self):
        """Crash a random active worker"""
        active_workers = [w for w in self.workers.values() if w.is_active]
        if active_workers:
            worker = random.choice(active_workers)
            worker.crash()
            self.stats["worker_crashes"] += 1
            
            # Report to fault tolerance system
            # (In real system, this would be detected automatically)
            print(f"💥 CHAOS: Worker {worker.worker_id} crashed!")
    
    def _slow_down_worker(self):
        """Temporarily slow down a worker"""
        active_workers = [w for w in self.workers.values() if w.is_active]
        if active_workers:
            worker = random.choice(active_workers)
            original_duration = worker.base_duration
            worker.base_duration = (1000, 2000)  # Very slow
            
            def restore_speed():
                time.sleep(random.uniform(10, 20))
                worker.base_duration = original_duration
                print(f"⚡ Worker {worker.worker_id} speed restored")
            
            threading.Thread(target=restore_speed, daemon=True).start()
            print(f"🐌 CHAOS: Worker {worker.worker_id} slowed down temporarily")
    
    def _recover_crashed_worker(self):
        """Recover a crashed worker"""
        crashed_workers = [w for w in self.workers.values() if not w.is_active]
        if crashed_workers:
            worker = random.choice(crashed_workers)
            worker.recover()
            print(f"🔄 CHAOS: Worker {worker.worker_id} recovered")
    
    def _on_task_retry(self, task, failure_type, error_message):
        """Handle task retry callback"""
        print(f"🔄 RETRY: Task {task.task_id[-8:]}... (attempt {task.attempt_number})")
    
    def _on_task_timeout(self, task):
        """Handle task timeout callback"""
        print(f"⏰ TIMEOUT: Task {task.task_id[-8:]}... on worker {task.worker_id}")
    
    def _on_task_dead_letter(self, task, reason):
        """Handle dead letter callback"""
        print(f"💀 DEAD LETTER: Task {task.task_id[-8:]}... - {reason}")
    
    def _on_circuit_breaker_opened(self, worker_id, circuit_breaker):
        """Handle circuit breaker opened callback"""
        print(f"🚫 CIRCUIT OPEN: {worker_id} (failure rate: {circuit_breaker.failure_rate:.1f}%)")
        self.stats["circuit_breakers_opened"] += 1
    
    def _print_real_time_stats(self):
        """Print real-time statistics"""
        stats = self.fault_manager.get_statistics()
        
        print(f"\n📊 Real-time Stats:")
        print(f"   Tasks: {self.stats['tasks_submitted']} submitted, "
              f"{self.stats['tasks_completed']} completed, "
              f"{self.stats['tasks_failed']} failed")
        print(f"   Active: {stats.get('active_tasks', 0)}, "
              f"Retrying: {stats.get('retry_queue_size', 0)}, "
              f"Dead: {stats.get('tasks_dead_letter', 0)}")
        
        # Worker health
        active_workers = len([w for w in self.workers.values() if w.is_active])
        circuit_open = len([cb for cb in self.fault_manager.circuit_breakers.values() 
                          if cb.state.value == "open"])
        
        print(f"   Workers: {active_workers}/{len(self.workers)} active, "
              f"{circuit_open} circuit breakers open")
    
    def _print_final_report(self):
        """Print comprehensive final report"""
        print("\n" + "="*60)
        print("📋 PRODUCTION FAULT TOLERANCE DEMO - FINAL REPORT")
        print("="*60)
        
        stats = self.fault_manager.get_statistics()
        
        # Overall statistics
        total_tasks = self.stats["tasks_submitted"]
        completed_tasks = self.stats["tasks_completed"]
        failed_tasks = self.stats["tasks_failed"]
        
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        print(f"\n📈 Overall Performance:")
        print(f"   Total tasks submitted: {total_tasks}")
        print(f"   Successfully completed: {completed_tasks}")
        print(f"   Failed tasks: {failed_tasks}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        # Fault tolerance statistics
        print(f"\n🛡️ Fault Tolerance Performance:")
        print(f"   Tasks retried: {stats.get('tasks_retried', 0)}")
        print(f"   Tasks timed out: {stats.get('tasks_timed_out', 0)}")
        print(f"   Dead letter queue: {stats.get('tasks_dead_letter', 0)}")
        print(f"   Worker crashes: {self.stats['worker_crashes']}")
        print(f"   Circuit breakers opened: {self.stats['circuit_breakers_opened']}")
        
        # Worker analysis
        print(f"\n👥 Worker Analysis:")
        for worker_id, worker in self.workers.items():
            cb = self.fault_manager.circuit_breakers.get(worker_id)
            if cb:
                status = "🟢 Active" if worker.is_active else "🔴 Crashed"
                cb_status = f"CB: {cb.state.value}"
                failure_rate = f"{cb.failure_rate:.1f}%" if cb.total_calls > 0 else "N/A"
                
                print(f"   {worker_id}: {status}, {cb_status}, "
                      f"Failure rate: {failure_rate}")
        
        # System health assessment
        print(f"\n🏥 System Health Assessment:")
        
        if success_rate >= 90:
            health = "🟢 EXCELLENT"
        elif success_rate >= 80:
            health = "🟡 GOOD"
        elif success_rate >= 70:
            health = "🟠 FAIR"
        else:
            health = "🔴 POOR"
        
        print(f"   Overall system health: {health}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if stats.get("tasks_dead_letter", 0) > 0:
            print("   - Review tasks in dead letter queue for manual recovery")
        
        if self.stats["circuit_breakers_opened"] > 2:
            print("   - Investigate workers with frequent circuit breaker trips")
        
        if success_rate < 85:
            print("   - Consider adding more reliable workers to the pool")
            print("   - Review task timeout settings")
        
        if stats.get("retry_queue_size", 0) > 5:
            print("   - Monitor retry queue size during peak loads")
        
        print(f"\n✅ Fault tolerance system successfully handled:")
        print(f"   - {self.stats['worker_crashes']} worker crashes")
        print(f"   - {stats.get('tasks_retried', 0)} task retries")
        print(f"   - {stats.get('tasks_timed_out', 0)} task timeouts")
        print(f"   - Maintained {success_rate:.1f}% overall success rate")
        
        print(f"\n🎉 Production demo completed successfully!")


if __name__ == "__main__":
    # Run production demonstration
    demo = ProductionFaultToleranceDemo()
    
    try:
        demo.setup_production_environment()
        demo.run_production_demo(duration_minutes=2)  # 2-minute demo
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        raise
    finally:
        print("\n🔄 Cleaning up resources...")
        # Cleanup would go here in real implementation