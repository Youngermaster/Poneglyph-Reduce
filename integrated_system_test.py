#!/usr/bin/env python3
"""
Complete Integration Test for Poneglyph-Reduce System
Tests the full pipeline: gRPC Middleware + MQTT + Redis + Java Master + C++ Workers
"""

import subprocess
import sys
import time
import os
import signal
import threading
import requests
import json
from pathlib import Path

class PoneglyphSystemIntegrator:
    def __init__(self):
        self.processes = []
        self.base_path = Path(__file__).parent
        self.middleware_path = self.base_path / "middleware"
        self.road_poneglyph_path = self.base_path / "Road-Poneglyph"
        self.poneglyph_path = self.base_path / "Poneglyph"
        
    def start_process(self, name, cmd, cwd=None, env=None):
        """Start a subprocess and track it"""
        print(f"🚀 Starting {name}...")
        try:
            process = subprocess.Popen(
                cmd, 
                cwd=cwd, 
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            self.processes.append((name, process))
            print(f"✅ {name} started (PID: {process.pid})")
            return process
        except Exception as e:
            print(f"❌ Failed to start {name}: {e}")
            return None
    
    def stop_all_processes(self):
        """Stop all tracked processes"""
        print("\n🛑 Stopping all processes...")
        for name, process in reversed(self.processes):
            try:
                if process.poll() is None:  # Process still running
                    print(f"   Stopping {name}...")
                    if os.name == 'nt':
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    print(f"✅ {name} stopped")
            except Exception as e:
                print(f"⚠️  Error stopping {name}: {e}")

    def wait_for_service(self, url, timeout=30, service_name="Service"):
        """Wait for a service to be ready"""
        print(f"⏳ Waiting for {service_name} to be ready...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code < 500:
                    print(f"✅ {service_name} is ready!")
                    return True
            except:
                pass
            time.sleep(1)
        print(f"❌ {service_name} failed to start within {timeout}s")
        return False

    def run_grpc_middleware(self):
        """Start the updated gRPC middleware with EMQX integration"""
        env = os.environ.copy()
        env.update({
            "PONEGLYPH_GRPC_PORT": "50051",
            "PONEGLYPH_METRICS_PORT": "8080", 
            "PONEGLYPH_FT_API_PORT": "8083",
            "PONEGLYPH_USE_DYNAMODB": "false",  # Use local storage for testing
            "PONEGLYPH_MQTT_BROKER": "localhost",
            "PONEGLYPH_MQTT_PORT": "1883",
        })
        
        return self.start_process(
            "gRPC Middleware (EMQX + Fault Tolerance)",
            [sys.executable, "server.py"],
            cwd=self.middleware_path,
            env=env
        )

    def run_java_master(self):
        """Start the Java master with gRPC integration"""
        # Check if gradlew exists and build first
        gradlew = self.road_poneglyph_path / ("gradlew.bat" if os.name == 'nt' else "gradlew")
        if not gradlew.exists():
            print("❌ Gradle wrapper not found")
            return None

        # Build the project
        print("🔨 Building Java master...")
        build_result = subprocess.run(
            [str(gradlew), "build", "-x", "test"],
            cwd=self.road_poneglyph_path,
            capture_output=True,
            text=True
        )
        
        if build_result.returncode != 0:
            print(f"❌ Java build failed: {build_result.stderr}")
            return None
        
        # Run the GrpcIntegratedMain
        return self.start_process(
            "Java Master (gRPC Integrated)",
            [str(gradlew), "run", "--args=GrpcIntegratedMain"],
            cwd=self.road_poneglyph_path
        )

    def build_cpp_workers(self):
        """Build the C++ workers"""
        print("🔨 Building C++ Workers...")
        try:
            build_dir = self.poneglyph_path / "build"
            build_dir.mkdir(exist_ok=True)
            
            # Run cmake
            cmake_result = subprocess.run(
                ["cmake", ".."],
                cwd=build_dir,
                capture_output=True,
                text=True
            )
            
            if cmake_result.returncode != 0:
                print(f"❌ CMake failed: {cmake_result.stderr}")
                return False
            
            # Build
            if os.name == 'nt':
                build_result = subprocess.run(
                    ["cmake", "--build", ".", "--config", "Release"],
                    cwd=build_dir,
                    capture_output=True,
                    text=True
                )
            else:
                build_result = subprocess.run(
                    ["make", "-j4"],
                    cwd=build_dir,
                    capture_output=True,
                    text=True
                )
            
            if build_result.returncode == 0:
                print("✅ C++ Workers built successfully")
                return True
            else:
                print(f"❌ Build failed: {build_result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Build error: {e}")
            return False

    def run_cpp_worker(self, worker_id=1):
        """Start a C++ worker"""
        build_dir = self.poneglyph_path / "build"
        executable = build_dir / ("Poneglyph.exe" if os.name == 'nt' else "Poneglyph")
        
        if not executable.exists():
            print(f"❌ Worker executable not found: {executable}")
            return None
        
        env = os.environ.copy()
        env["PONEGLYPH_MASTER_URL"] = "http://localhost:8080"  # Connect to Java master
        
        return self.start_process(
            f"C++ Worker-{worker_id}",
            [str(executable)],
            cwd=build_dir,
            env=env
        )

    def run_integration_test(self):
        """Run a complete integration test"""
        print("🧪 Running integration test...")
        
        # Test 1: Health check
        if not self._test_health_endpoints():
            return False
        
        # Test 2: Submit a MapReduce job
        if not self._test_mapreduce_job():
            return False
        
        # Test 3: Monitor job completion
        if not self._test_job_monitoring():
            return False
            
        print("🎉 Integration test PASSED!")
        return True

    def _test_health_endpoints(self):
        """Test that all services are healthy"""
        endpoints = [
            ("Java Master Health", "http://localhost:8080/api/health"),
            ("Middleware Metrics", "http://localhost:8080/metrics"),
            ("Fault Tolerance API", "http://localhost:8083/fault-tolerance/health"),
        ]
        
        for name, url in endpoints:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {name}: OK")
                else:
                    print(f"❌ {name}: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ {name}: {e}")
                return False
        
        return True

    def _test_mapreduce_job(self):
        """Test MapReduce job submission and processing"""
        # Word count example
        map_script = '''
import sys

def map_function(input_file):
    with open(input_file, 'r') as f:
        for line in f:
            words = line.strip().split()
            for word in words:
                print(f"{word.lower()}\\t1")

if __name__ == "__main__":
    map_function(sys.argv[1])
'''
        
        reduce_script = '''
import sys
from collections import defaultdict

def reduce_function(input_file):
    word_counts = defaultdict(int)
    
    with open(input_file, 'r') as f:
        for line in f:
            if '\\t' in line:
                word, count = line.strip().split('\\t', 1)
                word_counts[word] += int(count)
    
    for word, count in sorted(word_counts.items()):
        print(f"{word}: {count}")

if __name__ == "__main__":
    reduce_function(sys.argv[1])
'''
        
        job_data = {
            "map_script": map_script,
            "reduce_script": reduce_script,
            "input_data": "hello world hello python world programming python"
        }
        
        try:
            response = requests.post(
                "http://localhost:8080/api/jobs",
                json=job_data,
                timeout=10
            )
            
            if response.status_code in [200, 202]:
                result = response.json()
                job_id = result.get("job_id")
                print(f"✅ Job submitted successfully: {job_id}")
                return True
            else:
                print(f"❌ Job submission failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Job submission error: {e}")
            return False

    def _test_job_monitoring(self):
        """Test job status monitoring"""
        try:
            # Check job status
            response = requests.get("http://localhost:8080/api/jobs/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Job monitoring: {status}")
                return True
            else:
                print(f"❌ Job monitoring failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Job monitoring error: {e}")
            return False

    def run_complete_integration(self):
        """Run the complete integrated system"""
        print("🌟 Poneglyph Complete System Integration")
        print("=" * 50)
        print("Components:")
        print("🔧 gRPC Middleware (EMQX + Fault Tolerance + Redis)")
        print("☕ Java Master (gRPC Integration)")
        print("⚡ C++ Workers (HTTP with gRPC backend)")
        print("📊 Metrics & Monitoring")
        print("=" * 50)
        
        try:
            # 1. Start gRPC middleware
            if not self.run_grpc_middleware():
                return False
            
            # Wait for middleware to be ready
            if not self.wait_for_service("http://localhost:8080/health", service_name="gRPC Middleware"):
                return False
            
            # 2. Start Java master
            if not self.run_java_master():
                return False
            
            # Wait for Java master to be ready
            if not self.wait_for_service("http://localhost:8080/api/health", service_name="Java Master"):
                return False
            
            # 3. Build C++ workers
            if not self.build_cpp_workers():
                return False
            
            # 4. Start multiple workers
            worker_count = 2
            for i in range(1, worker_count + 1):
                if not self.run_cpp_worker(i):
                    print(f"❌ Failed to start worker {i}")
                    return False
                time.sleep(2)  # Stagger startup
            
            # 5. Wait for workers to register
            print("⏳ Waiting for workers to register...")
            time.sleep(5)
            
            # 6. Run integration tests
            if not self.run_integration_test():
                return False
            
            # 7. Keep system running for monitoring
            print("\n🎉 Complete system integration successful!")
            print("🔍 System is running. Check the following:")
            print("   📊 Metrics: http://localhost:8080/metrics")
            print("   🛡️  Fault Tolerance: http://localhost:8083/fault-tolerance/dashboard")
            print("   ☕ Java Master API: http://localhost:8080/api/health")
            print("   📈 Job Status: http://localhost:8080/api/jobs/status")
            print("\n⏹️  Press Ctrl+C to stop all services")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(10)
                    # Quick health check
                    try:
                        response = requests.get("http://localhost:8080/api/health", timeout=2)
                        if response.status_code != 200:
                            print("⚠️  System health check failed")
                            break
                    except:
                        print("⚠️  System appears to be down")
                        break
            except KeyboardInterrupt:
                print("\n👋 Shutting down requested by user")
            
            return True
            
        except Exception as e:
            print(f"❌ Integration failed: {e}")
            return False
        finally:
            self.stop_all_processes()

def main():
    """Main function"""
    integrator = PoneglyphSystemIntegrator()
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n🛑 Shutting down...")
        integrator.stop_all_processes()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Poneglyph Complete System Integration")
        print("Usage: python integrated_system_test.py")
        print("\nThis script will:")
        print("1. 🚀 Start gRPC middleware with EMQX integration")
        print("2. ☕ Start Java master with gRPC communication")
        print("3. ⚡ Build and start C++ workers")
        print("4. 🧪 Run integration tests")
        print("5. 🔍 Monitor system health")
        sys.exit(0)
    
    success = integrator.run_complete_integration()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()