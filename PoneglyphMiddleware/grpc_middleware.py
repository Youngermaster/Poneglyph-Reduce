#!/usr/bin/env python3
"""
Poneglyph gRPC Middleware Server
Implements gRPC services for job management, worker coordination and task distribution
"""

import json
import logging
import os
import time
import threading
import uuid
from concurrent import futures
from typing import Dict, List, Optional

import grpc
import pika
import redis

# Import generated gRPC classes
import poneglyph_pb2
import poneglyph_pb2_grpc

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class PoneglyphJobManagementService(poneglyph_pb2_grpc.JobManagementServiceServicer):
    """Job Management Service Implementation"""
    
    def __init__(self, middleware):
        self.middleware = middleware

    def SubmitJob(self, request, context):
        """Submit a new MapReduce job"""
        try:
            job_id = request.job_id or f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # Create job data
            job_data = {
                "job_id": job_id,
                "input_text": request.input_text,
                "map_script": request.map_script.decode('utf-8') if request.map_script else "",
                "reduce_script": request.reduce_script.decode('utf-8') if request.reduce_script else "",
                "split_size": request.split_size or 1000,
                "reducers": request.reducers or 1,
                "status": "PENDING",
                "created_at": time.time(),
                "maps_total": 0,
                "maps_completed": 0,
                "reduces_total": request.reducers or 1,
                "reduces_completed": 0
            }
            
            # Store job in Redis
            self.middleware.redis_client.hset(f"job:{job_id}", mapping=job_data)
            
            # Create map tasks
            input_lines = request.input_text.strip().split('\n')
            chunk_size = request.split_size or len(input_lines)
            map_tasks = []
            
            for i in range(0, len(input_lines), chunk_size):
                chunk = input_lines[i:i + chunk_size]
                task_id = f"{job_id}_map_{len(map_tasks)}"
                
                task = {
                    "task_id": task_id,
                    "job_id": job_id,
                    "type": "MAP",
                    "script": request.map_script.decode('utf-8') if request.map_script else "",
                    "input_data": chunk,
                    "created_at": time.time()
                }
                
                map_tasks.append(task)
                
                # Publish task to RabbitMQ
                self.middleware.rabbitmq.publish('poneglyph_tasks', task)
            
            # Update job with task count
            job_data["maps_total"] = len(map_tasks)
            self.middleware.redis_client.hset(f"job:{job_id}", mapping={"maps_total": len(map_tasks)})
            
            logger.info(f"Job {job_id} submitted with {len(map_tasks)} map tasks")
            
            return poneglyph_pb2.SubmitJobResponse(
                success=True,
                job_id=job_id,
                estimated_map_tasks=len(map_tasks),
                message=f"Job submitted successfully with {len(map_tasks)} map tasks"
            )
            
        except Exception as e:
            logger.error(f"Error submitting job: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to submit job: {str(e)}")
            return poneglyph_pb2.SubmitJobResponse(
                success=False,
                job_id="",
                estimated_map_tasks=0,
                message=f"Error: {str(e)}"
            )

    def GetJobStatus(self, request, context):
        """Get job status and progress"""
        try:
            job_data = self.middleware.redis_client.hgetall(f"job:{request.job_id}")
            
            if not job_data:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Job {request.job_id} not found")
                return poneglyph_pb2.JobStatusResponse()
            
            # Convert byte strings to regular strings
            job_info = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v 
                       for k, v in job_data.items()}
            
            # Map status to enum
            status_map = {
                "PENDING": poneglyph_pb2.JOB_PENDING,
                "RUNNING": poneglyph_pb2.JOB_RUNNING,
                "SUCCEEDED": poneglyph_pb2.JOB_SUCCEEDED,
                "FAILED": poneglyph_pb2.JOB_FAILED,
                "CANCELLED": poneglyph_pb2.JOB_CANCELLED
            }
            
            maps_total = int(job_info.get("maps_total", 0))
            maps_completed = int(job_info.get("maps_completed", 0))
            reduces_total = int(job_info.get("reduces_total", 0))
            reduces_completed = int(job_info.get("reduces_completed", 0))
            
            # Calculate progress
            total_tasks = maps_total + reduces_total
            completed_tasks = maps_completed + reduces_completed
            progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            return poneglyph_pb2.JobStatusResponse(
                job_id=request.job_id,
                state=status_map.get(job_info.get("status", "PENDING"), poneglyph_pb2.JOB_PENDING),
                maps_total=maps_total,
                maps_completed=maps_completed,
                reduces_total=reduces_total,
                reduces_completed=reduces_completed,
                progress_percentage=progress
            )
            
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get job status: {str(e)}")
            return poneglyph_pb2.JobStatusResponse()


class PoneglyphWorkerManagementService(poneglyph_pb2_grpc.WorkerManagementServiceServicer):
    """Worker Management Service Implementation"""
    
    def __init__(self, middleware):
        self.middleware = middleware

    def RegisterWorker(self, request, context):
        """Register a new worker"""
        try:
            worker_id = f"worker_{request.worker_name}_{uuid.uuid4().hex[:8]}"
            
            worker_data = {
                "worker_id": worker_id,
                "worker_name": request.worker_name,
                "capacity": request.capacity,
                "capabilities": json.dumps(request.capabilities),
                "status": "IDLE",
                "last_heartbeat": time.time(),
                "location": request.location,
                "current_tasks": 0
            }
            
            # Store worker in Redis
            self.middleware.redis_client.hset(f"worker:{worker_id}", mapping=worker_data)
            self.middleware.redis_client.sadd("active_workers", worker_id)
            self.middleware.redis_client.expire(f"worker:{worker_id}", 300)  # 5 minute expiry
            
            logger.info(f"Worker registered: {worker_id} ({request.worker_name})")
            
            return poneglyph_pb2.RegisterWorkerResponse(
                worker_id=worker_id,
                poll_interval_ms=5000,  # 5 seconds
                success=True,
                message=f"Worker {worker_id} registered successfully"
            )
            
        except Exception as e:
            logger.error(f"Error registering worker: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to register worker: {str(e)}")
            return poneglyph_pb2.RegisterWorkerResponse(
                success=False,
                message=f"Error: {str(e)}"
            )

    def SendHeartbeat(self, request, context):
        """Process worker heartbeat"""
        try:
            # Update worker info
            worker_data = {
                "last_heartbeat": time.time(),
                "status": "IDLE" if request.status == poneglyph_pb2.WORKER_IDLE else "BUSY",
                "current_tasks": len(request.running_tasks)
            }
            
            self.middleware.redis_client.hset(f"worker:{request.worker_id}", mapping=worker_data)
            self.middleware.redis_client.expire(f"worker:{request.worker_id}", 300)
            
            return poneglyph_pb2.HeartbeatResponse(
                acknowledged=True,
                next_heartbeat_interval=5000
            )
            
        except Exception as e:
            logger.error(f"Error processing heartbeat: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to process heartbeat: {str(e)}")
            return poneglyph_pb2.HeartbeatResponse(acknowledged=False)


class PoneglyphTaskDistributionService(poneglyph_pb2_grpc.TaskDistributionServiceServicer):
    """Task Distribution Service Implementation"""
    
    def __init__(self, middleware):
        self.middleware = middleware

    def RequestTask(self, request, context):
        """Worker requests a task"""
        try:
            # Get task from RabbitMQ
            task_data = self.middleware.rabbitmq.get('poneglyph_tasks')
            
            if not task_data:
                return poneglyph_pb2.TaskResponse(
                    has_task=False,
                    message="No tasks available"
                )
            
            # Create gRPC Task message
            task = poneglyph_pb2.Task(
                task_id=task_data["task_id"],
                job_id=task_data["job_id"],
                type=poneglyph_pb2.TASK_MAP if task_data["type"] == "MAP" else poneglyph_pb2.TASK_REDUCE,
                payload=json.dumps({
                    "script": task_data["script"],
                    "input_data": task_data["input_data"]
                }).encode('utf-8')
            )
            
            logger.info(f"Assigned task {task_data['task_id']} to worker {request.worker_id}")
            
            return poneglyph_pb2.TaskResponse(
                has_task=True,
                task=task,
                message=f"Task {task_data['task_id']} assigned"
            )
            
        except Exception as e:
            logger.error(f"Error requesting task: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get task: {str(e)}")
            return poneglyph_pb2.TaskResponse(has_task=False, message=f"Error: {str(e)}")

    def CompleteTask(self, request, context):
        """Worker completes a task"""
        try:
            # Update job progress
            if request.result.success:
                # Increment completed count
                job_key = f"job:{request.job_id}"
                if request.task_type == poneglyph_pb2.TASK_MAP:
                    self.middleware.redis_client.hincrby(job_key, "maps_completed", 1)
                elif request.task_type == poneglyph_pb2.TASK_REDUCE:
                    self.middleware.redis_client.hincrby(job_key, "reduces_completed", 1)
                
                # Store result
                result_data = {
                    "task_id": request.task_id,
                    "job_id": request.job_id,
                    "worker_id": request.worker_id,
                    "success": True,
                    "result_data": request.result.result_data.decode('utf-8'),
                    "completed_at": time.time()
                }
                
                self.middleware.redis_client.hset(f"result:{request.task_id}", mapping=result_data)
                
                logger.info(f"Task {request.task_id} completed successfully by {request.worker_id}")
            else:
                logger.error(f"Task {request.task_id} failed: {request.result.error_message}")
            
            return poneglyph_pb2.TaskCompletionResponse(
                acknowledged=True,
                message="Task completion acknowledged"
            )
            
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to complete task: {str(e)}")
            return poneglyph_pb2.TaskCompletionResponse(acknowledged=False, message=f"Error: {str(e)}")


class RabbitMQManager:
    """RabbitMQ connection and operation manager"""
    
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self._lock = threading.Lock()
        self.setup()
    
    def setup(self):
        """Setup RabbitMQ connection with retries"""
        max_retries = 10
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to RabbitMQ (attempt {attempt + 1}/{max_retries})")
                self.connection = pika.BlockingConnection(pika.URLParameters(self.rabbitmq_url))
                self.channel = self.connection.channel()
                
                # Declare queues
                self.channel.queue_declare(queue='poneglyph_tasks', durable=True)
                self.channel.queue_declare(queue='poneglyph_results', durable=True)
                
                logger.info("RabbitMQ connection established")
                return
                
            except Exception as e:
                logger.warning(f"RabbitMQ connection failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("All RabbitMQ connection attempts failed")
                    raise
    
    def publish(self, queue: str, message: dict):
        """Publish message to queue"""
        try:
            with self._lock:
                if self.connection and not self.connection.is_closed:
                    self.channel.basic_publish(
                        exchange='',
                        routing_key=queue,
                        body=json.dumps(message),
                        properties=pika.BasicProperties(delivery_mode=2)
                    )
                    logger.debug(f"Published to {queue}: {message.get('task_id', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
    
    def get(self, queue: str) -> Optional[dict]:
        """Get message from queue"""
        try:
            with self._lock:
                if self.connection and not self.connection.is_closed:
                    method, properties, body = self.channel.basic_get(queue=queue)
                    if method:
                        message = json.loads(body.decode('utf-8'))
                        self.channel.basic_ack(delivery_tag=method.delivery_tag)
                        return message
        except Exception as e:
            logger.error(f"Failed to get message from {queue}: {e}")
        return None


class PoneglyphMiddleware:
    """Main middleware orchestrator"""
    
    def __init__(self):
        # Configuration
        self.rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://poneglyph:poneglyph123@rabbitmq:5672/')
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        self.grpc_port = int(os.getenv('GRPC_PORT', '50051'))
        
        # Initialize services
        self.redis_client = redis.from_url(self.redis_url)
        self.rabbitmq = RabbitMQManager(self.rabbitmq_url)
        
        # Test connections
        self.redis_client.ping()
        logger.info("Redis connection established")
        
        # gRPC server
        self.server = None
        
        logger.info("Poneglyph gRPC Middleware initialized")
    
    def start_grpc_server(self):
        """Start the gRPC server"""
        try:
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            
            # Add services
            poneglyph_pb2_grpc.add_JobManagementServiceServicer_to_server(
                PoneglyphJobManagementService(self), self.server
            )
            poneglyph_pb2_grpc.add_WorkerManagementServiceServicer_to_server(
                PoneglyphWorkerManagementService(self), self.server
            )
            poneglyph_pb2_grpc.add_TaskDistributionServiceServicer_to_server(
                PoneglyphTaskDistributionService(self), self.server
            )
            
            # Listen on port
            listen_addr = f'0.0.0.0:{self.grpc_port}'
            self.server.add_insecure_port(listen_addr)
            
            self.server.start()
            logger.info(f"gRPC server started on {listen_addr}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start gRPC server: {e}")
            return False
    
    def run(self):
        """Run the middleware"""
        logger.info("Starting Poneglyph gRPC Middleware...")
        
        if not self.start_grpc_server():
            logger.error("Failed to start gRPC server, exiting")
            return
        
        try:
            # Keep the server running
            while True:
                time.sleep(10)
                
                # Health check log
                active_workers = self.redis_client.scard("active_workers")
                logger.info(f"Middleware status: {active_workers} active workers")
                
        except KeyboardInterrupt:
            logger.info("Shutting down middleware...")
        except Exception as e:
            logger.error(f"Middleware error: {e}")
        finally:
            if self.server:
                self.server.stop(grace=5)
                logger.info("gRPC server stopped")


def main():
    middleware = PoneglyphMiddleware()
    middleware.run()


if __name__ == '__main__':
    main()
