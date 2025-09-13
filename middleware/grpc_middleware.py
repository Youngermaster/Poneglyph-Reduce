import os
import sys
import json
import time
import threading
import base64
from concurrent import futures
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import grpc
from grpc_tools import protoc

from middleware.config import get_config, GENERATED_DIR, PROTO_PATH
from middleware.state_store import StateStore
from middleware.dynamodb_state_store import DynamoDBStateStore
from middleware.mqtt_bridge import MqttBridge
from middleware.metrics_collector import get_metrics_collector, initialize_metrics
from middleware.metrics_server import MetricsHTTPServer
from middleware.load_balancer import get_load_balancer, initialize_load_balancer, LoadBalancingStrategy

# S3 support (optional)
try:
    import boto3
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

# Get configuration
config = get_config()
GEN_DIR = str(GENERATED_DIR)  # Compatibility with existing code

class S3Helper:
    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.enabled = S3_AVAILABLE and self.bucket
        if self.enabled:
            try:
                self.s3_client = boto3.client('s3', region_name=self.region)
                print(f"S3Helper: using bucket {self.bucket}")
            except Exception as e:
                print(f"S3Helper: initialization failed ({e})")
                self.enabled = False
        else:
            print("S3Helper: disabled (no bucket or boto3 missing)")
    
    def upload_script(self, job_id: str, script_type: str, script_content: bytes) -> str:
        """Upload map or reduce script to S3 and return URL"""
        if not self.enabled:
            return f"local://{script_type}_script"  # fallback
        
        key = f"jobs/{job_id}/{script_type}_script.py"
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=script_content,
                ContentType="text/x-python"
            )
            return f"s3://{self.bucket}/{key}"
        except Exception as e:
            print(f"S3Helper: upload failed ({e})")
            return f"local://{script_type}_script"  # fallback

# Ensure generated modules exist
os.makedirs(GEN_DIR, exist_ok=True)
if not (os.path.exists(os.path.join(GEN_DIR, "poneglyph_pb2.py")) and os.path.exists(os.path.join(GEN_DIR, "poneglyph_pb2_grpc.py"))):
    protoc.main([
        "",
        f"-I{os.path.dirname(PROTO_PATH)}",
        f"--python_out={GEN_DIR}",
        f"--grpc_python_out={GEN_DIR}",
        PROTO_PATH,
    ])

import sys
sys.path.insert(0, GEN_DIR)
import poneglyph_pb2  # type: ignore
import poneglyph_pb2_grpc  # type: ignore


class WorkerManagementService(poneglyph_pb2_grpc.WorkerManagementServiceServicer):
    def __init__(self, state: StateStore, mqtt: MqttBridge):
        self.state = state
        self.mqtt = mqtt
        self.worker_ttl = 60  # Workers expire after 60 seconds without heartbeat
        self.health_scores = {}  # Track worker performance metrics
        self.metrics = get_metrics_collector()
        self.load_balancer = get_load_balancer()

    def RegisterWorker(self, request, context):
        worker_id = request.worker_name or f"worker-{int(time.time()*1000)}"
        current_time = int(time.time() * 1000)
        info = {
            "worker_id": worker_id,
            "worker_name": request.worker_name,
            "capacity": request.capacity,
            "capabilities": list(request.capabilities),
            "location": request.location,
            "status": "IDLE",
            "registered_at": current_time,
            "last_heartbeat": current_time,
            "health_score": 100,  # Start with perfect health
            "task_count": 0,
            "success_count": 0,
            "failure_count": 0
        }
        self.state.upsert_worker(worker_id, info)
        self.health_scores[worker_id] = 100
        
        # Register worker with load balancer
        self.load_balancer.register_worker(
            worker_id=worker_id,
            capacity=request.capacity,
            health_score=100
        )
        
        # Record metrics
        self.metrics.record_counter("worker_registrations")
        self.metrics.update_worker_metrics(
            worker_id, 
            health_score=100, 
            capacity=request.capacity,
            tasks_completed=0,
            tasks_failed=0
        )
        
        print(f"Worker registered: {worker_id} with health score 100")
        return poneglyph_pb2.RegisterWorkerResponse(worker_id=worker_id, poll_interval_ms=1000, success=True, message="Registered")

    def SendHeartbeat(self, request, context):
        current_time = int(time.time() * 1000)
        
        # Get existing worker data to preserve metrics
        existing_worker = self.state.get_worker(request.worker_id) or {}
        
        info = {
            "worker_id": request.worker_id,
            "status": poneglyph_pb2.WorkerStatus.Name(request.status),
            "running_tasks": list(request.running_tasks),
            "last_heartbeat": current_time,
            # Preserve existing metrics
            "health_score": existing_worker.get("health_score", 100),
            "task_count": existing_worker.get("task_count", 0),
            "success_count": existing_worker.get("success_count", 0),
            "failure_count": existing_worker.get("failure_count", 0)
        }
        
        # Update health score based on heartbeat consistency
        self._update_health_on_heartbeat(request.worker_id, existing_worker)
        
        self.state.upsert_worker(request.worker_id, info)
        
        # Update load balancer with heartbeat info
        health_score = existing_worker.get("health_score", 100)
        self.load_balancer.update_worker_heartbeat(
            worker_id=request.worker_id,
            health_score=health_score
        )
        
        # Record metrics
        self.metrics.record_counter("worker_heartbeats")
        self.metrics.update_worker_metrics(request.worker_id, last_heartbeat=current_time)
        
        return poneglyph_pb2.HeartbeatResponse(acknowledged=True, commands=[], next_heartbeat_interval=1000)

    def GetWorkerStatus(self, request, context):
        data = self.state.get_worker(request.worker_id) or {}
        
        # Check if worker is still alive (within TTL)
        current_time = int(time.time() * 1000)
        last_heartbeat = int(data.get("last_heartbeat", 0) or 0)
        ttl_threshold = current_time - (self.worker_ttl * 1000)
        is_healthy = last_heartbeat > ttl_threshold and data.get("health_score", 0) > 50
        
        wi = poneglyph_pb2.WorkerInfo(
            worker_id=data.get("worker_id", request.worker_id),
            worker_name=data.get("worker_name", ""),
            capacity=int(data.get("capacity", 0) or 0),
            location=data.get("location", ""),
            status=poneglyph_pb2.WORKER_IDLE if is_healthy else poneglyph_pb2.WORKER_OFFLINE,
            last_heartbeat=last_heartbeat,
            current_tasks=len(data.get("running_tasks", [])),
        )
        
        return poneglyph_pb2.WorkerStatusResponse(
            worker=wi, 
            is_healthy=is_healthy, 
            last_heartbeat=last_heartbeat
        )

    def UnregisterWorker(self, request, context):
        # Clean up worker data and health scores
        worker_data = self.state.get_worker(request.worker_id)
        if worker_data:
            # Mark as offline instead of deleting (for audit trail)
            worker_data["status"] = "OFFLINE"
            worker_data["unregistered_at"] = int(time.time() * 1000)
            self.state.upsert_worker(request.worker_id, worker_data)
        
        # Remove from health score tracking
        if request.worker_id in self.health_scores:
            del self.health_scores[request.worker_id]
        
        print(f"Worker unregistered: {request.worker_id}")
        return poneglyph_pb2.UnregisterWorkerResponse(success=True, message="Unregistered")

    def _update_health_on_heartbeat(self, worker_id, existing_worker):
        """Update health score based on heartbeat consistency"""
        if not existing_worker:
            return
        
        current_time = int(time.time() * 1000)
        last_heartbeat = existing_worker.get("last_heartbeat", 0)
        
        # Calculate time since last heartbeat
        time_diff = current_time - last_heartbeat
        expected_interval = 1000  # 1 second expected heartbeat interval
        
        # Improve health for consistent heartbeats
        if time_diff <= expected_interval * 1.5:  # Within 1.5x expected interval
            self._improve_health_score(worker_id, 1)
        elif time_diff <= expected_interval * 3:  # Within 3x expected interval
            # Neutral - no change
            pass
        else:
            # Degrade health for late heartbeats
            self._degrade_health_score(worker_id, 5)

    def _improve_health_score(self, worker_id, amount=2):
        """Improve worker health score"""
        current_score = self.health_scores.get(worker_id, 100)
        new_score = min(100, current_score + amount)
        self.health_scores[worker_id] = new_score
        
        worker = self.state.get_worker(worker_id)
        if worker:
            worker["health_score"] = new_score
            self.state.upsert_worker(worker_id, worker)

    def _degrade_health_score(self, worker_id, amount=10):
        """Degrade worker health score"""
        current_score = self.health_scores.get(worker_id, 100)
        new_score = max(0, current_score - amount)
        self.health_scores[worker_id] = new_score
        
        worker = self.state.get_worker(worker_id)
        if worker:
            worker["health_score"] = new_score
            self.state.upsert_worker(worker_id, worker)

    def update_worker_performance(self, worker_id, success):
        """Update worker performance metrics - called by TaskDistribution service"""
        worker = self.state.get_worker(worker_id)
        if worker:
            worker["task_count"] = worker.get("task_count", 0) + 1
            if success:
                worker["success_count"] = worker.get("success_count", 0) + 1
                self._improve_health_score(worker_id, 3)  # Reward successful tasks
            else:
                worker["failure_count"] = worker.get("failure_count", 0) + 1
                self._degrade_health_score(worker_id, 15)  # Penalize failures more
            
            self.state.upsert_worker(worker_id, worker)
            
            # Log performance update
            success_rate = worker["success_count"] / max(1, worker["task_count"])
            health = worker["health_score"]
            print(f"Worker {worker_id} performance: {success_rate:.2%} success rate, health: {health}")


class JobManagementService(poneglyph_pb2_grpc.JobManagementServiceServicer):
    def __init__(self, state: StateStore, mqtt: MqttBridge, s3_helper: S3Helper):
        self.state = state
        self.mqtt = mqtt
        self.load_balancer = get_load_balancer()
        self.s3_helper = s3_helper
        self.metrics = get_metrics_collector()

    def SubmitJob(self, request, context):
        job_id = request.job_id or f"job-{int(time.time()*1000)}"
        
        # Upload scripts to S3 if provided
        map_script_url = None
        reduce_script_url = None
        
        if request.map_script:
            map_script_url = self.s3_helper.upload_script(job_id, "map", request.map_script)
        
        if request.reduce_script:
            reduce_script_url = self.s3_helper.upload_script(job_id, "reduce", request.reduce_script)
        
        # Split input into chunks (basic implementation)
        input_chunks = self._split_input(request.input_text, request.split_size or 100)
        map_tasks = len(input_chunks)
        
        # Save job state
        self.state.upsert_job(job_id, {
            "job_id": job_id,
            "state": poneglyph_pb2.JobState.Name(poneglyph_pb2.JOB_PENDING),
            "maps_total": map_tasks,
            "reduces_total": request.reducers or 1,
            "map_script_url": map_script_url,
            "reduce_script_url": reduce_script_url,
            "input_format": request.format,
        })
        
        # Record job submission metrics
        self.metrics.record_counter("jobs_submitted")
        self.metrics.record_job_state_change(job_id, "NONE", "PENDING")
        self.metrics.update_job_progress(job_id, map_tasks, 0, 0)
        
        # Generate MAP tasks with intelligent load balancing
        for i, chunk in enumerate(input_chunks):
            task = {
                "task_id": f"{job_id}-map-{i}",
                "job_id": job_id,
                "type": "MAP",
                "payload": chunk,
                "map_script_url": map_script_url,
                "capabilities": ["MAP"],
                "retry_count": 0
            }
            
            # Use load balancer to select optimal worker
            selected_worker = self.load_balancer.select_worker_for_task(
                task_type="MAP",
                preferred_capabilities=["MAP"]
            )
            
            if selected_worker:
                # Send task to specific worker
                self.mqtt.publish_task(selected_worker, task)
                
                # Report task assignment to load balancer
                self.load_balancer.report_task_assignment(selected_worker, task["task_id"])
                
                print(f"Task {task['task_id']} assigned to worker {selected_worker}")
            else:
                # Fallback to broadcast if no suitable worker found
                print(f"No suitable worker found for task {task['task_id']}, broadcasting")
                self.mqtt.broadcast_task(task)
        
        # Record task generation
        self.metrics.record_counter("tasks_generated", value=map_tasks)
        
        return poneglyph_pb2.SubmitJobResponse(success=True, job_id=job_id, estimated_map_tasks=map_tasks, message=f"Job submitted with {map_tasks} map tasks")
    
    def _split_input(self, input_text: str, chunk_size: int = 100):
        """Split input text into chunks of approximately chunk_size characters"""
        if not input_text:
            return [""]
        
        words = input_text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks or [""]

    def GetJobStatus(self, request, context):
        data = self.state.get_job(request.job_id) or {}
        return poneglyph_pb2.JobStatusResponse(
            job_id=request.job_id,
            state=poneglyph_pb2.JOB_RUNNING,
            maps_total=int(data.get("maps_total", 1) or 1),
            maps_completed=0,
            reduces_total=int(data.get("reduces_total", 0) or 0),
            reduces_completed=0,
            progress_percentage=0.3,
            estimated_completion_time=int(time.time()*1000)+10000,
        )

    def GetJobResult(self, request, context):
        return poneglyph_pb2.JobResultResponse(ready=False, result_data="", result_url="", message="Not implemented")

    def CancelJob(self, request, context):
        return poneglyph_pb2.CancelJobResponse(success=True, message="Cancelled (noop)")


class TaskDistributionService(poneglyph_pb2_grpc.TaskDistributionServiceServicer):
    def __init__(self, state: StateStore, mqtt: MqttBridge, worker_service):
        self.state = state
        self.mqtt = mqtt
        self.worker_service = worker_service  # Reference to update worker health
        self.metrics = get_metrics_collector()
        self.load_balancer = get_load_balancer()

    def RequestTask(self, request, context):
        # Enhanced: check for tasks matching worker capabilities
        worker = self.state.get_worker(request.worker_id)
        if not worker:
            return poneglyph_pb2.TaskResponse(has_task=False, message="Worker not registered")
        
        # For now, still recommend MQTT push model
        return poneglyph_pb2.TaskResponse(has_task=False, message="Use MQTT push model")

    def CompleteTask(self, request, context):
        # Enhanced: update job progress
        task_id = request.task_id
        job_id = request.job_id
        success = request.result.success
        
        print(f"Task completed: worker={request.worker_id} task={task_id} job={job_id} success={success}")
        
        # Update job progress
        job = self.state.get_job(job_id) or {}
        if job:
            maps_completed = int(job.get("maps_completed", 0))
            maps_total = int(job.get("maps_total", 1))
            
            if request.task_type == poneglyph_pb2.TASK_MAP and success:
                maps_completed += 1
                progress = (maps_completed / maps_total) * 100
                
                job["maps_completed"] = maps_completed
                job["progress_percentage"] = progress
                
                if maps_completed >= maps_total:
                    job["state"] = poneglyph_pb2.JobState.Name(poneglyph_pb2.JOB_SUCCEEDED)
                else:
                    job["state"] = poneglyph_pb2.JobState.Name(poneglyph_pb2.JOB_RUNNING)
                
                self.state.upsert_job(job_id, job)
                print(f"Job {job_id} progress: {maps_completed}/{maps_total} ({progress:.1f}%)")
        
        # Calculate task duration if provided
        task_duration = getattr(request, 'execution_time_ms', 0) or 1000  # Default 1s if not provided
        
        # Record task completion metrics
        self.metrics.record_task_completion(
            worker_id=request.worker_id,
            job_id=job_id,
            success=success,
            duration_ms=task_duration
        )
        
        # Update load balancer with task completion
        self.load_balancer.report_task_completion(
            worker_id=request.worker_id,
            task_id=task_id,
            duration_ms=task_duration,
            success=success
        )
        
        # Update worker performance metrics
        if self.worker_service:
            self.worker_service.update_worker_performance(request.worker_id, success)
        
        # Store task result (basic implementation)
        result_key = f"result_{task_id}"
        self.state.upsert_job(result_key, {
            "task_id": task_id,
            "job_id": job_id,
            "worker_id": request.worker_id,
            "result": request.result.result_data.decode('utf-8', errors='ignore') if request.result.result_data else "",
            "success": success,
            "completed_at": int(time.time() * 1000)
        })
        
        return poneglyph_pb2.TaskCompletionResponse(acknowledged=True, message="Result stored")

    def ReportTaskProgress(self, request, context):
        print(f"Task progress: worker={request.worker_id} task={request.task_id} progress={request.progress_percentage}%")
        return poneglyph_pb2.TaskProgressResponse(acknowledged=True)


class ResourceManagementService(poneglyph_pb2_grpc.ResourceManagementServiceServicer):
    def __init__(self, state):
        self.state = state

    def GetClusterResources(self, request, context):
        # Enhanced implementation using DynamoDB statistics
        try:
            if hasattr(self.state, 'get_cluster_stats'):
                stats = self.state.get_cluster_stats()
                all_workers = self.state.get_all_workers()
            else:
                # Fallback for legacy state store
                workers = self.state.list_workers()
                all_workers = {f"worker-{i}": w for i, w in enumerate(workers)}
                stats = {
                    'total_workers': len(workers),
                    'active_workers': len(workers),
                    'running_jobs': 0,
                    'pending_jobs': 0
                }
            
            # Calculate resource totals from active workers
            total_cpu = 0
            total_memory = 0
            active_count = 0
            
            current_time = int(time.time() * 1000)
            ttl_threshold = current_time - 60000  # 60 seconds TTL
            
            for worker_data in all_workers.values():
                if isinstance(worker_data, dict):
                    last_heartbeat = int(worker_data.get('last_heartbeat', 0))
                    if last_heartbeat > ttl_threshold:
                        active_count += 1
                        capacity = int(worker_data.get('capacity', 1))
                        total_cpu += capacity
                        total_memory += capacity * 1024
            
            return poneglyph_pb2.ClusterResourcesResponse(
                total_resources=poneglyph_pb2.ClusterResourceInfo(
                    total_workers=stats['total_workers'],
                    active_workers=active_count,
                    total_cpu_cores=total_cpu,
                    total_memory_mb=total_memory
                ),
                available_resources=poneglyph_pb2.ClusterResourceInfo(
                    available_cpu_cores=total_cpu,
                    available_memory_mb=total_memory
                )
            )
        except Exception as e:
            print(f"GetClusterResources error: {e}")
            return poneglyph_pb2.ClusterResourcesResponse(
                total_resources=poneglyph_pb2.ClusterResourceInfo(total_workers=0, active_workers=0)
            )

    def AllocateResources(self, request, context):
        return poneglyph_pb2.ResourceAllocationResponse(allocated=True, allocated_workers=[], message="Resources allocated")

    def ReleaseResources(self, request, context):
        return poneglyph_pb2.ResourceReleaseResponse(success=True)


def on_mqtt_message(topic: str, payload: bytes):
    try:
        if topic.endswith("/register"):
            data = json.loads(payload.decode())
            print(f"MQTT Register from {data.get('worker_id')}")
        elif topic.endswith("/heartbeat"):
            data = json.loads(payload.decode())
            print(f"MQTT Heartbeat from {data.get('worker_id')}")
        elif topic.startswith("gridmr/results/"):
            data = json.loads(payload.decode())
            print(f"MQTT Result for {data.get('job_id')}: {str(data)[:120]}")
    except Exception as e:
        print(f"on_mqtt_message error: {e}")


def serve():
    port = int(os.getenv("GRPC_PORT", "50051"))
    metrics_port = int(os.getenv("METRICS_PORT", "8080"))
    
    # Initialize metrics system
    initialize_metrics(retention_minutes=60)
    print("Metrics system initialized")
    
    # Initialize load balancer with smart composite strategy
    initialize_load_balancer(LoadBalancingStrategy.SMART_COMPOSITE)
    print("Load balancer initialized with SMART_COMPOSITE strategy")
    
    # Initialize state store (DynamoDB preferred, fallback to memory/Redis)
    use_dynamodb = os.getenv("USE_DYNAMODB", "true").lower() == "true"
    
    if use_dynamodb:
        print("Initializing DynamoDB state store...")
        state = DynamoDBStateStore()
        # Try to create tables if they don't exist
        state.create_tables_if_not_exist()
    else:
        print("Using legacy state store (Redis/Memory)...")
        state = StateStore()
    
    s3_helper = S3Helper()
    mqtt = MqttBridge(on_mqtt_message)
    mqtt.start()
    
    # Start metrics HTTP server
    metrics_server = MetricsHTTPServer(port=metrics_port)
    metrics_server.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Create service instances with cross-references for health tracking
    worker_service = WorkerManagementService(state, mqtt)
    job_service = JobManagementService(state, mqtt, s3_helper)
    task_service = TaskDistributionService(state, mqtt, worker_service)
    resource_service = ResourceManagementService(state)
    
    # Add services to server
    poneglyph_pb2_grpc.add_WorkerManagementServiceServicer_to_server(worker_service, server)
    poneglyph_pb2_grpc.add_JobManagementServiceServicer_to_server(job_service, server)
    poneglyph_pb2_grpc.add_TaskDistributionServiceServicer_to_server(task_service, server)
    poneglyph_pb2_grpc.add_ResourceManagementServiceServicer_to_server(resource_service, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC middleware listening on :{port}")
    print(f"Metrics server listening on :{metrics_port}")
    print("Available endpoints:")
    print(f"  - http://localhost:{metrics_port}/metrics (Prometheus)")
    print(f"  - http://localhost:{metrics_port}/metrics/json (JSON)")
    print(f"  - http://localhost:{metrics_port}/health (Health check)")
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print("Shutting down servers...")
        server.stop(0)
        metrics_server.stop()
        get_metrics_collector().stop()


if __name__ == "__main__":
    serve()
