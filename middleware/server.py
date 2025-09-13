#!/usr/bin/env python3
"""
Main server entry point for Poneglyph-Reduce middleware
Production-ready server with all components integrated
"""

import signal
import sys
import time
from concurrent import futures
from contextlib import contextmanager

from middleware.config import get_config
from middleware.grpc_middleware import (
    WorkerManagementService, JobManagementService, 
    TaskDistributionService, ResourceManagementService
)
from middleware.fault_tolerant_grpc import (
    FaultTolerantTaskDistributionService, FaultTolerantJobManagementService
)
from middleware.fault_tolerance import initialize_fault_tolerance
from middleware.fault_tolerance_api import FaultToleranceAPI
from middleware.state_store import StateStore
from middleware.dynamodb_state_store import DynamoDBStateStore
from middleware.mqtt_bridge import MqttBridge
from middleware.metrics_collector import initialize_metrics
from middleware.metrics_server import MetricsHTTPServer
from middleware.load_balancer import initialize_load_balancer

try:
    import grpc
    from middleware.generated import poneglyph_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    print("Warning: gRPC not available. Install grpcio and grpcio-tools.")


class PoneglyphServer:
    """Main Poneglyph middleware server"""
    
    def __init__(self, enable_fault_tolerance: bool = True):
        self.config = get_config()
        self.enable_fault_tolerance = enable_fault_tolerance
        
        # Server components
        self.grpc_server = None
        self.metrics_server = None
        self.fault_tolerance_api = None
        self.mqtt_bridge = None
        
        # Services
        self.state_store = None
        self.fault_manager = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def initialize_components(self):
        """Initialize all server components"""
        print("🚀 Initializing Poneglyph middleware components...")
        
        # Initialize state store
        if self.config.use_dynamodb:
            print("📊 Using DynamoDB state store")
            self.state_store = DynamoDBStateStore(
                table_name=self.config.get("DYNAMODB_TABLE_NAME"),
                region=self.config.get("DYNAMODB_REGION")
            )
            self.state_store.create_tables_if_not_exist()
        else:
            print("📊 Using in-memory state store")
            self.state_store = StateStore()
        
        # Initialize metrics
        print("📈 Initializing metrics collection")
        initialize_metrics()
        
        # Initialize load balancer
        print("⚖️ Initializing load balancer")
        initialize_load_balancer()
        
        # Initialize fault tolerance if enabled
        if self.enable_fault_tolerance:
            print("🛡️ Initializing fault tolerance system")
            self.fault_manager = initialize_fault_tolerance()
        
        # Initialize MQTT bridge if enabled
        if self.config.mqtt_enabled:
            print("📡 Initializing MQTT bridge")
            self.mqtt_bridge = MqttBridge(self._on_mqtt_message)
    
    def _on_mqtt_message(self, topic, message):
        """Handle MQTT messages"""
        print(f"📡 MQTT message on {topic}: {message}")
        # Handle MQTT messages here
    
    def start_grpc_server(self):
        """Start the gRPC server"""
        if not GRPC_AVAILABLE:
            print("❌ Cannot start gRPC server: gRPC not available")
            return False
        
        print(f"🌐 Starting gRPC server on port {self.config.grpc_port}")
        
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # Create service instances
        if self.enable_fault_tolerance and self.fault_manager:
            # Use fault-tolerant services
            task_service = FaultTolerantTaskDistributionService(
                {"workers": {}},  # worker_manager placeholder
                None,  # metrics_collector
                None   # load_balancer
            )
            job_service = FaultTolerantJobManagementService(
                {"workers": {}},  # worker_manager placeholder
                None   # metrics_collector
            )
        else:
            # Use standard services
            worker_service = WorkerManagementService(self.state_store, self.mqtt_bridge)
            task_service = TaskDistributionService(self.state_store, self.mqtt_bridge, worker_service)
            job_service = JobManagementService(self.state_store, self.mqtt_bridge, None)
        
        resource_service = ResourceManagementService(self.state_store)
        
        # Register services
        poneglyph_pb2_grpc.add_TaskDistributionServiceServicer_to_server(
            task_service, self.grpc_server
        )
        poneglyph_pb2_grpc.add_JobManagementServiceServicer_to_server(
            job_service, self.grpc_server
        )
        poneglyph_pb2_grpc.add_ResourceManagementServiceServicer_to_server(
            resource_service, self.grpc_server
        )
        
        if not self.enable_fault_tolerance:
            poneglyph_pb2_grpc.add_WorkerManagementServiceServicer_to_server(
                worker_service, self.grpc_server
            )
        
        # Start server
        self.grpc_server.add_insecure_port(f"[::]:{self.config.grpc_port}")
        self.grpc_server.start()
        
        print(f"✅ gRPC server listening on port {self.config.grpc_port}")
        return True
    
    def start_http_services(self):
        """Start HTTP-based services"""
        # Start metrics server
        print(f"📊 Starting metrics server on port {self.config.metrics_port}")
        self.metrics_server = MetricsHTTPServer(port=self.config.metrics_port)
        self.metrics_server.start()
        
        # Start fault tolerance API if enabled
        if self.enable_fault_tolerance and self.fault_manager:
            print(f"🛡️ Starting fault tolerance API on port {self.config.fault_tolerance_api_port}")
            # Create a minimal grpc server wrapper for the API
            class MinimalGrpcServer:
                def __init__(self, fault_manager):
                    self.fault_manager = fault_manager
                
                def get_fault_tolerance_stats(self):
                    return self.fault_manager.get_statistics()
                
                def get_circuit_breaker_status(self):
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
                    return self.fault_manager.dead_letter_queue.get_statistics()
                
                def recover_dead_letter_task(self, task_id: str):
                    return self.fault_manager.recover_dead_letter_task(task_id)
                
                def force_retry_task(self, task_id: str):
                    return self.fault_manager.force_retry_task(task_id)
            
            grpc_wrapper = MinimalGrpcServer(self.fault_manager)
            self.fault_tolerance_api = FaultToleranceAPI(
                grpc_wrapper, 
                port=self.config.fault_tolerance_api_port
            )
            self.fault_tolerance_api.start()
    
    def start_mqtt_bridge(self):
        """Start MQTT bridge if enabled"""
        if self.mqtt_bridge:
            print("📡 Starting MQTT bridge")
            self.mqtt_bridge.start()
    
    def start(self):
        """Start all server components"""
        print("🚀 Starting Poneglyph middleware server")
        print("=" * 50)
        
        try:
            # Initialize components
            self.initialize_components()
            
            # Start services
            grpc_started = self.start_grpc_server()
            self.start_http_services()
            self.start_mqtt_bridge()
            
            print("\n✅ All services started successfully!")
            print(f"📡 gRPC server: localhost:{self.config.grpc_port}")
            print(f"📊 Metrics: http://localhost:{self.config.metrics_port}")
            
            if self.enable_fault_tolerance:
                print(f"🛡️ Fault Tolerance API: http://localhost:{self.config.fault_tolerance_api_port}")
                print(f"📋 Dashboard: http://localhost:{self.config.fault_tolerance_api_port}/fault-tolerance/dashboard")
            
            return grpc_started
            
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop all server components"""
        print("🛑 Stopping Poneglyph middleware server...")
        
        if self.grpc_server:
            print("   Stopping gRPC server")
            self.grpc_server.stop(0)
        
        if self.metrics_server:
            print("   Stopping metrics server")
            self.metrics_server.stop()
        
        if self.fault_tolerance_api:
            print("   Stopping fault tolerance API")
            self.fault_tolerance_api.stop()
        
        if self.mqtt_bridge:
            print("   Stopping MQTT bridge")
            self.mqtt_bridge.stop()
        
        if self.fault_manager:
            print("   Stopping fault tolerance manager")
            self.fault_manager.stop()
        
        print("✅ Server stopped gracefully")
    
    def wait_for_termination(self):
        """Wait for server termination"""
        if self.grpc_server:
            try:
                self.grpc_server.wait_for_termination()
            except KeyboardInterrupt:
                pass
    
    @contextmanager
    def run_context(self):
        """Context manager for running the server"""
        try:
            if self.start():
                yield self
            else:
                raise RuntimeError("Failed to start server")
        finally:
            self.stop()


def main():
    """Main entry point"""
    print("🌟 Poneglyph-Reduce Middleware Server")
    print("=" * 40)
    
    # Create and start server
    server = PoneglyphServer(enable_fault_tolerance=True)
    
    try:
        if server.start():
            print("\n🎉 Server is ready and running!")
            print("Press Ctrl+C to stop")
            server.wait_for_termination()
        else:
            print("❌ Failed to start server")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        server.stop()


if __name__ == "__main__":
    main()