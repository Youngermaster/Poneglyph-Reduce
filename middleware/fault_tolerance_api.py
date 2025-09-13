#!/usr/bin/env python3
"""
HTTP API for Fault Tolerance Management
Provides REST endpoints to monitor and manage fault tolerance features
"""

from flask import Flask, jsonify, request
import threading
from middleware.fault_tolerance import get_fault_tolerance_manager
from middleware.fault_tolerant_grpc import FaultTolerantPoneglyphGrpcServer


class FaultToleranceAPI:
    """HTTP API for fault tolerance monitoring and management"""
    
    def __init__(self, grpc_server: FaultTolerantPoneglyphGrpcServer, port=8083):
        self.app = Flask(__name__)
        self.grpc_server = grpc_server
        self.fault_manager = get_fault_tolerance_manager()
        self.port = port
        self.server_thread = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """System health check"""
            return jsonify({
                "status": "healthy",
                "fault_tolerance": "active",
                "timestamp": int(time.time() * 1000)
            })
        
        @self.app.route('/fault-tolerance/stats', methods=['GET'])
        def get_fault_tolerance_stats():
            """Get comprehensive fault tolerance statistics"""
            return jsonify(self.fault_manager.get_statistics())
        
        @self.app.route('/fault-tolerance/circuit-breakers', methods=['GET'])
        def get_circuit_breakers():
            """Get circuit breaker status for all workers"""
            return jsonify(self.grpc_server.get_circuit_breaker_status())
        
        @self.app.route('/fault-tolerance/circuit-breaker/<worker_id>', methods=['GET'])
        def get_circuit_breaker(worker_id):
            """Get specific circuit breaker status"""
            circuit_breaker = self.fault_manager.circuit_breakers.get(worker_id)
            if not circuit_breaker:
                return jsonify({"error": "Worker not found"}), 404
            
            return jsonify({
                "worker_id": worker_id,
                "state": circuit_breaker.state.value,
                "failure_count": circuit_breaker.failure_count,
                "failure_rate": circuit_breaker.failure_rate,
                "total_calls": circuit_breaker.total_calls,
                "total_successes": circuit_breaker.total_successes,
                "total_failures": circuit_breaker.total_failures,
                "can_execute": circuit_breaker.can_execute(),
                "last_failure_time": circuit_breaker.last_failure_time,
                "last_success_time": circuit_breaker.last_success_time
            })
        
        @self.app.route('/fault-tolerance/dead-letter-queue', methods=['GET'])
        def get_dead_letter_queue():
            """Get dead letter queue status and tasks"""
            dlq_stats = self.grpc_server.get_dead_letter_queue_status()
            
            # Get task details
            limit = request.args.get('limit', type=int)
            tasks = self.fault_manager.dead_letter_queue.get_tasks(limit)
            
            task_details = []
            for task in tasks:
                task_details.append({
                    "task_id": task.task_id,
                    "job_id": task.job_id,
                    "worker_id": task.worker_id,
                    "failure_count": task.failure_count,
                    "failure_type": task.failure_type.value if task.failure_type else None,
                    "failure_message": task.failure_message,
                    "last_failure_time": task.last_failure_time,
                    "reason": self.fault_manager.dead_letter_queue.task_reasons.get(task.task_id, "Unknown")
                })
            
            return jsonify({
                "statistics": dlq_stats,
                "tasks": task_details
            })
        
        @self.app.route('/fault-tolerance/tasks/<task_id>', methods=['GET'])
        def get_task_status(task_id):
            """Get detailed status of a specific task"""
            task_status = self.fault_manager.get_task_status(task_id)
            if not task_status:
                return jsonify({"error": "Task not found"}), 404
            
            return jsonify(task_status)
        
        @self.app.route('/fault-tolerance/tasks/<task_id>/retry', methods=['POST'])
        def force_retry_task(task_id):
            """Force retry a specific task"""
            success = self.grpc_server.force_retry_task(task_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": f"Task {task_id} scheduled for retry"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": f"Task {task_id} not found or cannot be retried"
                }), 400
        
        @self.app.route('/fault-tolerance/dead-letter-queue/<task_id>/recover', methods=['POST'])
        def recover_dead_letter_task(task_id):
            """Recover task from dead letter queue"""
            success = self.grpc_server.recover_dead_letter_task(task_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": f"Task {task_id} recovered from dead letter queue"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": f"Task {task_id} not found in dead letter queue"
                }), 400
        
        @self.app.route('/fault-tolerance/workers/<worker_id>/circuit-breaker/reset', methods=['POST'])
        def reset_circuit_breaker(worker_id):
            """Reset circuit breaker for a worker"""
            circuit_breaker = self.fault_manager.circuit_breakers.get(worker_id)
            if not circuit_breaker:
                return jsonify({"error": "Worker not found"}), 404
            
            # Reset circuit breaker
            circuit_breaker.state = circuit_breaker.state.CLOSED
            circuit_breaker.failure_count = 0
            circuit_breaker.half_open_calls = 0
            
            return jsonify({
                "success": True,
                "message": f"Circuit breaker reset for worker {worker_id}"
            })
        
        @self.app.route('/fault-tolerance/active-tasks', methods=['GET'])
        def get_active_tasks():
            """Get all active tasks"""
            tasks = []
            for task_id, task in self.fault_manager.active_tasks.items():
                tasks.append({
                    "task_id": task.task_id,
                    "job_id": task.job_id,
                    "worker_id": task.worker_id,
                    "state": task.state.value,
                    "attempt_number": task.attempt_number,
                    "assigned_at": task.assigned_at,
                    "started_at": task.started_at,
                    "is_expired": task.is_expired,
                    "can_retry": task.can_retry,
                    "failure_count": task.failure_count
                })
            
            return jsonify({
                "total_active_tasks": len(tasks),
                "tasks": tasks
            })
        
        @self.app.route('/fault-tolerance/retry-queue', methods=['GET'])
        def get_retry_queue():
            """Get retry queue status"""
            retry_tasks = []
            current_time = int(time.time() * 1000)
            
            for retry_time, task_id in self.fault_manager.retry_queue:
                task = self.fault_manager.active_tasks.get(task_id)
                if task:
                    retry_tasks.append({
                        "task_id": task_id,
                        "job_id": task.job_id,
                        "retry_time": retry_time,
                        "time_until_retry": max(0, retry_time - current_time),
                        "attempt_number": task.attempt_number,
                        "failure_count": task.failure_count,
                        "failure_type": task.failure_type.value if task.failure_type else None
                    })
            
            return jsonify({
                "total_retry_tasks": len(retry_tasks),
                "tasks": retry_tasks
            })
        
        @self.app.route('/fault-tolerance/dashboard', methods=['GET'])
        def get_dashboard():
            """Get comprehensive dashboard data"""
            stats = self.fault_manager.get_statistics()
            circuit_breakers = self.grpc_server.get_circuit_breaker_status()
            dlq_stats = self.grpc_server.get_dead_letter_queue_status()
            
            # Calculate health metrics
            total_tasks = stats.get("tasks_total", 0)
            success_rate = 0
            if total_tasks > 0:
                completed = stats.get("tasks_completed", 0)
                success_rate = (completed / total_tasks) * 100
            
            # Circuit breaker summary
            cb_summary = {
                "total_workers": len(circuit_breakers),
                "open_circuits": len([cb for cb in circuit_breakers.values() if cb["state"] == "open"]),
                "half_open_circuits": len([cb for cb in circuit_breakers.values() if cb["state"] == "half_open"]),
                "healthy_workers": len([cb for cb in circuit_breakers.values() if cb["can_execute"]])
            }
            
            return jsonify({
                "overview": {
                    "success_rate": success_rate,
                    "total_tasks": total_tasks,
                    "active_tasks": stats.get("active_tasks", 0),
                    "retry_queue_size": stats.get("retry_queue_size", 0),
                    "dead_letter_count": stats.get("tasks_dead_letter", 0)
                },
                "circuit_breakers": cb_summary,
                "detailed_stats": stats,
                "dead_letter_queue": dlq_stats
            })
    
    def start(self):
        """Start HTTP API server"""
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(
                target=lambda: self.app.run(host='0.0.0.0', port=self.port, debug=False),
                daemon=True
            )
            self.server_thread.start()
            print(f"🌐 Fault Tolerance API running on http://localhost:{self.port}")
    
    def stop(self):
        """Stop HTTP API server"""
        # Flask doesn't have a clean shutdown mechanism in this setup
        # In production, use gunicorn or similar WSGI server
        pass


# Example usage
if __name__ == "__main__":
    import time
    
    # Start fault-tolerant gRPC server
    grpc_server = FaultTolerantPoneglyphGrpcServer(port=50051)
    grpc_server.start()
    
    # Start HTTP API
    api = FaultToleranceAPI(grpc_server, port=8083)
    api.start()
    
    print("🛡️ Fault-tolerant system running:")
    print("   gRPC server: localhost:50051")
    print("   HTTP API: http://localhost:8083")
    print("   Dashboard: http://localhost:8083/fault-tolerance/dashboard")
    
    try:
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down fault-tolerant system...")
        grpc_server.stop()
        api.stop()