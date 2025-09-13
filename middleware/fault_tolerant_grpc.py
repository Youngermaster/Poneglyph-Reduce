#!/usr/bin/env python3
"""
Integration of Fault Tolerance system with gRPC Middleware
Updates the main middleware to use fault tolerance and recovery features
"""

import time
import uuid
import grpc
from concurrent import futures
from middleware.fault_tolerance import (
    get_fault_tolerance_manager, TaskState, FailureType, 
    initialize_fault_tolerance
)
from middleware.grpc_middleware import (
    WorkerManagementService, JobManagementService, TaskDistributionService,
    ResourceManagementService
)


class FaultTolerantTaskDistributionService(TaskDistributionService):
    """Enhanced TaskDistributionService with fault tolerance"""
    
    def __init__(self, worker_manager, metrics_collector, load_balancer):
        super().__init__(worker_manager, metrics_collector, load_balancer)
        self.fault_manager = get_fault_tolerance_manager()
        
        # Setup fault tolerance callbacks
        self.fault_manager.on_task_retry = self._on_task_retry
        self.fault_manager.on_task_timeout = self._on_task_timeout
        self.fault_manager.on_task_dead_letter = self._on_task_dead_letter
        self.fault_manager.on_circuit_breaker_opened = self._on_circuit_breaker_opened
    
    def DistributeTask(self, request, context):
        """Distribute task with fault tolerance"""
        from middleware.generated.poneglyph_pb2 import TaskDistributionResponse
        
        task_id = request.task_id or str(uuid.uuid4())
        job_id = request.job_id
        
        print(f"🎯 Distributing task {task_id} for job {job_id}")
        
        # Register task with fault tolerance system
        task_execution = self.fault_manager.register_task(
            task_id=task_id,
            job_id=job_id,
            task_type=request.task_type,
            timeout_seconds=300  # 5 minutes
        )
        
        # Store task details
        task_execution.payload = request.payload
        task_execution.script_url = request.script_url
        task_execution.capabilities = list(request.required_capabilities)
        
        # Select worker using load balancer with circuit breaker awareness
        selected_worker = self._select_fault_tolerant_worker(request)
        
        if not selected_worker:
            return TaskDistributionResponse(
                success=False,
                message="No suitable workers available",
                task_id=task_id
            )
        
        # Assign task to worker through fault tolerance system
        if not self.fault_manager.assign_task_to_worker(task_id, selected_worker['worker_id']):
            return TaskDistributionResponse(
                success=False,
                message=f"Worker {selected_worker['worker_id']} circuit breaker is open",
                task_id=task_id
            )
        
        # Distribute to worker
        success = self._distribute_to_worker(selected_worker, request, task_id)
        
        if success:
            # Mark task as started
            self.fault_manager.start_task_execution(task_id)
            
            return TaskDistributionResponse(
                success=True,
                message=f"Task distributed to worker {selected_worker['worker_id']}",
                task_id=task_id,
                worker_id=selected_worker['worker_id']
            )
        else:
            # Handle immediate failure
            self.fault_manager.complete_task(
                task_id=task_id,
                success=False,
                error_message="Failed to distribute task to worker"
            )
            
            return TaskDistributionResponse(
                success=False,
                message="Failed to distribute task",
                task_id=task_id
            )
    
    def _select_fault_tolerant_worker(self, request):
        """Select worker considering circuit breaker states"""
        # Get all capable workers
        capable_workers = []
        for worker_id, worker_info in self.worker_manager.workers.items():
            if not worker_info.get('available', False):
                continue
            
            # Check capabilities
            worker_capabilities = set(worker_info.get('capabilities', []))
            required_capabilities = set(request.required_capabilities)
            
            if not required_capabilities.issubset(worker_capabilities):
                continue
            
            # Check circuit breaker
            circuit_breaker = self.fault_manager.get_or_create_circuit_breaker(worker_id)
            if not circuit_breaker.can_execute():
                print(f"🚫 Skipping worker {worker_id} - circuit breaker is open")
                continue
            
            capable_workers.append({
                'worker_id': worker_id,
                'worker_info': worker_info,
                'circuit_breaker': circuit_breaker
            })
        
        if not capable_workers:
            return None
        
        # Use load balancer to select best worker
        return self.load_balancer.select_worker_for_task({
            'task_type': request.task_type,
            'required_capabilities': list(request.required_capabilities)
        })
    
    def _distribute_to_worker(self, worker, request, task_id):
        """Distribute task to specific worker"""
        try:
            worker_info = worker['worker_info']
            
            # Simulate task distribution (replace with actual gRPC call)
            print(f"📤 Sending task {task_id} to worker {worker['worker_id']}")
            
            # Update worker metrics
            self.metrics_collector.record_task_assignment(
                worker['worker_id'], 
                request.task_type
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to distribute task {task_id} to worker {worker['worker_id']}: {e}")
            return False
    
    def _on_task_retry(self, task, failure_type, error_message):
        """Handle task retry callback"""
        print(f"🔄 Retrying task {task.task_id} due to {failure_type.value}")
        
        # Find new worker for retry
        request_mock = type('Request', (), {
            'task_id': task.task_id,
            'job_id': task.job_id,
            'task_type': task.task_type,
            'required_capabilities': task.capabilities,
            'payload': task.payload,
            'script_url': task.script_url
        })()
        
        selected_worker = self._select_fault_tolerant_worker(request_mock)
        if selected_worker:
            # Assign to new worker
            if self.fault_manager.assign_task_to_worker(task.task_id, selected_worker['worker_id']):
                success = self._distribute_to_worker(selected_worker, request_mock, task.task_id)
                if success:
                    self.fault_manager.start_task_execution(task.task_id)
                    print(f"✅ Task {task.task_id} retry assigned to worker {selected_worker['worker_id']}")
                else:
                    print(f"❌ Failed to redistribute task {task.task_id} on retry")
            else:
                print(f"🚫 Cannot assign retry task {task.task_id} - circuit breaker issues")
        else:
            print(f"⚠️ No workers available for task {task.task_id} retry")
    
    def _on_task_timeout(self, task):
        """Handle task timeout callback"""
        print(f"⏰ Task {task.task_id} timed out on worker {task.worker_id}")
        
        # Report worker as potentially problematic
        if task.worker_id:
            circuit_breaker = self.fault_manager.get_or_create_circuit_breaker(task.worker_id)
            print(f"⚠️ Worker {task.worker_id} timeout rate: {circuit_breaker.failure_rate:.1f}%")
    
    def _on_task_dead_letter(self, task, reason):
        """Handle task dead letter callback"""
        print(f"💀 Task {task.task_id} moved to dead letter queue: {reason}")
        
        # Notify job management about permanent failure
        # This could trigger job-level recovery strategies
    
    def _on_circuit_breaker_opened(self, worker_id, circuit_breaker):
        """Handle circuit breaker opened callback"""
        print(f"🚫 Circuit breaker OPENED for worker {worker_id}")
        print(f"   Failure rate: {circuit_breaker.failure_rate:.1f}%")
        print(f"   Total failures: {circuit_breaker.total_failures}")
        
        # Mark worker as temporarily unavailable
        if worker_id in self.worker_manager.workers:
            self.worker_manager.workers[worker_id]['circuit_breaker_open'] = True


class FaultTolerantJobManagementService(JobManagementService):
    """Enhanced JobManagementService with fault tolerance integration"""
    
    def __init__(self, worker_manager, metrics_collector):
        super().__init__(worker_manager, metrics_collector)
        self.fault_manager = get_fault_tolerance_manager()
    
    def CompleteTask(self, request, context):
        """Handle task completion with fault tolerance tracking"""
        from middleware.generated.poneglyph_pb2 import TaskCompletionResponse
        
        task_id = request.task_id
        success = request.success
        
        # Calculate duration
        duration_ms = int(time.time() * 1000) - (request.started_at or 0)
        
        # Complete task through fault tolerance system
        self.fault_manager.complete_task(
            task_id=task_id,
            success=success,
            duration_ms=duration_ms,
            error_message=request.error_message if not success else ""
        )
        
        # Update metrics
        self.metrics_collector.record_task_completion(
            request.worker_id,
            task_id,
            success,
            duration_ms
        )
        
        return TaskCompletionResponse(
            success=True,
            message="Task completion recorded"
        )
    
    def GetJobStatus(self, request, context):
        """Get job status including fault tolerance information"""
        from middleware.generated.poneglyph_pb2 import JobStatusResponse, TaskStatus
        
        response = super().GetJobStatus(request, context)
        
        # Enhance with fault tolerance data
        fault_stats = self.fault_manager.get_statistics()
        
        # Add fault tolerance metrics to response
        response.total_retries = fault_stats.get("tasks_retried", 0)
        response.total_timeouts = fault_stats.get("tasks_timed_out", 0)
        response.dead_letter_count = fault_stats.get("tasks_dead_letter", 0)
        
        return response


class FaultTolerantPoneglyphGrpcServer:
    """Enhanced gRPC server with integrated fault tolerance"""
    
    def __init__(self, port=50051):
        self.port = port
        self.server = None
        
        # Initialize fault tolerance first
        self.fault_manager = initialize_fault_tolerance()
        
        # Initialize other components (simplified)
        self.worker_manager = {"workers": {}}
        self.metrics_collector = None
        self.load_balancer = None
        
        print("🛡️ Fault-tolerant Poneglyph gRPC server initialized")
    
    def start(self):
        """Start the gRPC server with fault tolerance"""
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # Setup fault-tolerant services
        self._setup_services()
        
        self.server.add_insecure_port(f"[::]:{self.port}")
        self.server.start()
        print(f"🛡️ Fault-tolerant gRPC server listening on port {self.port}")
    
    def stop(self):
        """Stop the gRPC server"""
        if self.server:
            self.server.stop(0)
        if self.fault_manager:
            self.fault_manager.stop()
        print("🛡️ Fault-tolerant server stopped")
    
    def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            self.server.wait_for_termination()
    
    def _setup_services(self):
        """Setup services with fault tolerance integration"""
        from middleware.generated import poneglyph_pb2_grpc
        
        # Create fault-tolerant services
        self.task_distribution_service = FaultTolerantTaskDistributionService(
            self.worker_manager, 
            self.metrics_collector,
            self.load_balancer
        )
        
        self.job_management_service = FaultTolerantJobManagementService(
            self.worker_manager, 
            self.metrics_collector
        )
        
        # For simplicity, use standard worker management service
        self.worker_management_service = WorkerManagementService(None, None)
        
        # Register services
        poneglyph_pb2_grpc.add_WorkerManagementServiceServicer_to_server(
            self.worker_management_service, self.server
        )
        
        poneglyph_pb2_grpc.add_TaskDistributionServiceServicer_to_server(
            self.task_distribution_service, self.server
        )
        
        poneglyph_pb2_grpc.add_JobManagementServiceServicer_to_server(
            self.job_management_service, self.server
        )
    
    def get_fault_tolerance_stats(self):
        """Get comprehensive fault tolerance statistics"""
        return self.fault_manager.get_statistics()
    
    def get_circuit_breaker_status(self):
        """Get circuit breaker status for all workers"""
        stats = {}
        for worker_id, cb in self.fault_manager.circuit_breakers.items():
            stats[worker_id] = {
                "state": cb.state.value,
                "failure_rate": cb.failure_rate,
                "failure_count": cb.failure_count,
                "can_execute": cb.can_execute()
            }
        return stats
    
    def get_dead_letter_queue_status(self):
        """Get dead letter queue status"""
        return self.fault_manager.dead_letter_queue.get_statistics()
    
    def recover_dead_letter_task(self, task_id: str):
        """Recover a task from dead letter queue"""
        return self.fault_manager.recover_dead_letter_task(task_id)
    
    def force_retry_task(self, task_id: str):
        """Force retry a specific task"""
        return self.fault_manager.force_retry_task(task_id)


if __name__ == "__main__":
    # Start fault-tolerant server
    server = FaultTolerantPoneglyphGrpcServer(port=50051)
    
    try:
        server.start()
        print("🛡️ Fault-tolerant Poneglyph gRPC server running on port 50051")
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down fault-tolerant server...")
        server.stop()