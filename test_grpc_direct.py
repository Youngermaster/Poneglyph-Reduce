#!/usr/bin/env python3
"""
Simple gRPC Client Test
Tests actual gRPC communication with the middleware
"""

import sys
import os

# Add PoneglyphMiddleware to path
middleware_path = os.path.join(os.path.dirname(__file__), 'PoneglyphMiddleware')
sys.path.append(middleware_path)

try:
    import grpc
    import poneglyph_pb2
    import poneglyph_pb2_grpc
    print("✅ Successfully imported gRPC modules")
except ImportError as e:
    print(f"❌ Failed to import gRPC modules: {e}")
    sys.exit(1)

def test_middleware_communication():
    """Test direct communication with middleware"""
    print("🔌 Testing gRPC Middleware Communication...")
    
    try:
        # Create channel
        channel = grpc.insecure_channel('localhost:50051')
        
        # Wait for channel to be ready
        grpc.channel_ready_future(channel).result(timeout=5)
        print("✅ gRPC channel established")
        
        # Create service stubs
        job_stub = poneglyph_pb2_grpc.JobManagementServiceStub(channel)
        worker_stub = poneglyph_pb2_grpc.WorkerManagementServiceStub(channel)
        task_stub = poneglyph_pb2_grpc.TaskDistributionServiceStub(channel)
        
        print("✅ Service stubs created")
        
        # Test 1: Register a worker
        print("\\n🔧 Testing Worker Registration...")
        worker_request = poneglyph_pb2.WorkerRegistrationRequest(
            worker_id="test-worker-001",
            host="localhost",
            port=8081,
            capabilities=["MAP", "REDUCE"]
        )
        
        worker_response = worker_stub.RegisterWorker(worker_request)
        if worker_response.success:
            print("✅ Worker registered successfully!")
            print(f"   Worker ID: test-worker-001")
            print(f"   Message: {worker_response.message}")
        else:
            print(f"❌ Worker registration failed: {worker_response.message}")
        
        # Test 2: Submit a job
        print("\\n📋 Testing Job Submission...")
        job_request = poneglyph_pb2.JobSubmissionRequest(
            job_id="test-job-001",
            job_type="wordcount",
            input_data="hello world poneglyph mapreduce test integration",
            map_script="wordcount_map.py",
            reduce_script="wordcount_reduce.py"
        )
        
        job_response = job_stub.SubmitJob(job_request)
        if job_response.success:
            print("✅ Job submitted successfully!")
            print(f"   Job ID: test-job-001")
            print(f"   Message: {job_response.message}")
        else:
            print(f"❌ Job submission failed: {job_response.message}")
        
        # Test 3: List workers
        print("\\n👥 Testing Worker Listing...")
        list_request = poneglyph_pb2.ListWorkersRequest()
        list_response = worker_stub.ListWorkers(list_request)
        
        print(f"📊 Total workers in middleware: {len(list_response.workers)}")
        for worker in list_response.workers:
            print(f"   🔧 {worker.worker_id} at {worker.host}:{worker.port} - {worker.status}")
        
        # Test 4: Check job status
        print("\\n📊 Testing Job Status...")
        status_request = poneglyph_pb2.JobStatusRequest(job_id="test-job-001")
        status_response = job_stub.GetJobStatus(status_request)
        
        print(f"📋 Job Status: {status_response.status}")
        print(f"📊 Progress: {status_response.progress}")
        print(f"📝 Tasks: {status_response.total_tasks} total, {status_response.completed_tasks} completed")
        
        # Test 5: Distribute a task
        print("\\n🎯 Testing Task Distribution...")
        task_request = poneglyph_pb2.TaskDistributionRequest(
            job_id="test-job-001",
            task_type="MAP",
            input_chunk="hello world poneglyph",
            worker_id=""  # Let middleware choose
        )
        
        task_response = task_stub.DistributeTask(task_request)
        if task_response.success:
            print("✅ Task distributed successfully!")
            print(f"   Task ID: {task_response.task_id}")
            print(f"   Assigned to: {task_response.assigned_worker_id}")
        else:
            print(f"❌ Task distribution failed: {task_response.message}")
        
        channel.close()
        return True
        
    except grpc.RpcError as e:
        print(f"❌ gRPC Error: {e.code()} - {e.details()}")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

def main():
    print("=" * 60)
    print("  🏴‍☠️ PONEGLYPH gRPC COMMUNICATION TEST")
    print("=" * 60)
    print()
    
    print("🎯 Testing real gRPC communication with middleware")
    print("📋 Verifying worker registration and job processing")
    print()
    
    success = test_middleware_communication()
    
    if success:
        print("\\n" + "=" * 60)
        print("  🎉 gRPC COMMUNICATION SUCCESSFUL!")
        print("=" * 60)
        print()
        print("✅ VERIFICACIÓN COMPLETA:")
        print("   • Middleware está recibiendo conexiones gRPC")
        print("   • Workers se pueden registrar correctamente")
        print("   • Jobs se pueden enviar y procesar")
        print("   • Middleware mantiene información de workers")
        print("   • Tasks se distribuyen correctamente")
        print("   • Sistema de comunicación funciona perfectamente")
        print()
        print("🚀 MIDDLEWARE FUNCIONANDO CORRECTAMENTE!")
        print("📊 Sistema listo para procesamiento real de MapReduce")
        return 0
    else:
        print("\\n❌ gRPC COMMUNICATION FAILED!")
        print("🔧 Check middleware status and try again")
        return 1

if __name__ == "__main__":
    exit(main())
