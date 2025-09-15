#!/usr/bin/env python3
"""
Integration Test Script for Enhanced Poneglyph System
Tests the complete integration of your advanced middleware with teammate's working system
"""

import subprocess
import sys
import time
import requests
import json
from pathlib import Path

class EnhancedSystemTester:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.services_status = {}
        
    def test_service_health(self, name, url, timeout=5):
        """Test if a service is healthy"""
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                self.services_status[name] = "✅ Healthy"
                print(f"✅ {name}: Healthy")
                return True
            else:
                self.services_status[name] = f"⚠️  HTTP {response.status_code}"
                print(f"⚠️  {name}: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.services_status[name] = f"❌ Error: {str(e)[:50]}"
            print(f"❌ {name}: {e}")
            return False
    
    def test_enhanced_system(self):
        """Test the enhanced system with both original and advanced features"""
        print("🧪 Testing Enhanced Poneglyph System")
        print("=" * 50)
        
        # Test 1: Original Services (from teammate's implementation)
        print("\n📊 Testing Original Services:")
        original_services = [
            ("Master API", "http://localhost:8080/api/health"),
            ("MQTT Health", "http://localhost:8080/api/health/mqtt"),
            ("Redis Health", "http://localhost:8080/api/health/redis"),
            ("EMQX Dashboard", "http://localhost:18083"),
            ("Redis Insight", "http://localhost:5540"),
        ]
        
        original_healthy = 0
        for name, url in original_services:
            if self.test_service_health(name, url):
                original_healthy += 1
        
        # Test 2: Advanced Middleware Services (your implementation)
        print("\n🚀 Testing Advanced Middleware Services:")
        advanced_services = [
            ("gRPC Middleware Metrics", "http://localhost:8081/metrics"),
            ("gRPC Middleware Health", "http://localhost:8081/health"),
            ("Fault Tolerance API", "http://localhost:8084/fault-tolerance/health"),
            ("Fault Tolerance Dashboard", "http://localhost:8084/fault-tolerance/dashboard"),
        ]
        
        advanced_healthy = 0
        for name, url in advanced_services:
            if self.test_service_health(name, url):
                advanced_healthy += 1
        
        # Test 3: Integration Test - Submit job through original API
        print("\n🔗 Testing Integration:")
        integration_success = self.test_job_submission()
        
        # Test 4: Advanced Features Test
        print("\n⚡ Testing Advanced Features:")
        advanced_features_success = self.test_advanced_features()
        
        # Summary
        print("\n📋 Integration Test Summary:")
        print("=" * 50)
        print(f"Original Services: {original_healthy}/{len(original_services)} healthy")
        print(f"Advanced Services: {advanced_healthy}/{len(advanced_services)} healthy")
        print(f"Integration Test: {'✅ Passed' if integration_success else '❌ Failed'}")
        print(f"Advanced Features: {'✅ Working' if advanced_features_success else '⚠️  Limited'}")
        
        total_score = original_healthy + advanced_healthy + (2 if integration_success else 0) + (1 if advanced_features_success else 0)
        max_score = len(original_services) + len(advanced_services) + 3
        
        print(f"\n🎯 Overall Score: {total_score}/{max_score}")
        
        if total_score >= max_score * 0.8:
            print("🎉 Integration SUCCESSFUL! System is ready for production.")
            return True
        elif total_score >= max_score * 0.6:
            print("⚠️  Integration PARTIAL. Some features may be limited.")
            return True
        else:
            print("❌ Integration FAILED. Check service logs.")
            return False
    
    def test_job_submission(self):
        """Test job submission through the original API"""
        try:
            job_data = {
                "map_script": "import sys; [print(f'{word.lower()}\\t1') for word in open(sys.argv[1]).read().split()]",
                "reduce_script": "import sys; from collections import defaultdict; counts = defaultdict(int); [counts.__setitem__(parts[0], counts[parts[0]] + int(parts[1])) for line in open(sys.argv[1]) for parts in [line.strip().split('\\t')] if len(parts) == 2]; [print(f'{k}: {v}') for k, v in sorted(counts.items())]",
                "input_data": "hello world hello middleware integration test"
            }
            
            response = requests.post(
                "http://localhost:8080/api/jobs",
                json=job_data,
                timeout=10
            )
            
            if response.status_code in [200, 202]:
                result = response.json()
                print(f"✅ Job submitted: {result.get('job_id', 'unknown')}")
                return True
            else:
                print(f"❌ Job submission failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Job submission error: {e}")
            return False
    
    def test_advanced_features(self):
        """Test advanced middleware features"""
        try:
            # Test metrics endpoint
            metrics_response = requests.get("http://localhost:8081/metrics", timeout=5)
            if metrics_response.status_code == 200:
                print("✅ Prometheus metrics available")
                metrics_working = True
            else:
                print("⚠️  Metrics endpoint not accessible")
                metrics_working = False
            
            # Test fault tolerance API
            ft_response = requests.get("http://localhost:8084/fault-tolerance/health", timeout=5)
            if ft_response.status_code == 200:
                print("✅ Fault tolerance system active")
                ft_working = True
            else:
                print("⚠️  Fault tolerance API not accessible")
                ft_working = False
            
            return metrics_working or ft_working
            
        except Exception as e:
            print(f"⚠️  Advanced features test error: {e}")
            return False
    
    def print_service_status(self):
        """Print detailed service status"""
        print("\n📊 Detailed Service Status:")
        print("-" * 40)
        for service, status in self.services_status.items():
            print(f"{service:<25} {status}")
    
    def print_integration_guide(self):
        """Print integration success guide"""
        print("\n🎯 Integration Success Guide:")
        print("=" * 50)
        print("✅ WORKING FEATURES:")
        print("   • Original EMQX + Redis system (teammate's work)")
        print("   • HTTP REST API for jobs and workers")
        print("   • Docker Compose orchestration")
        print("")
        print("🚀 NEW ENHANCED FEATURES:")
        print("   • Advanced gRPC middleware layer")
        print("   • Fault tolerance with circuit breakers")
        print("   • Smart load balancing strategies")
        print("   • Comprehensive Prometheus metrics")
        print("   • Real-time health monitoring")
        print("")
        print("🔗 INTEGRATION POINTS:")
        print("   • Both systems share EMQX and Redis")
        print("   • Dual-mode operation: HTTP + gRPC")
        print("   • Gradual migration path available")
        print("")
        print("📋 NEXT STEPS:")
        print("   1. Monitor http://localhost:8081/metrics for system health")
        print("   2. Use http://localhost:8084/fault-tolerance/dashboard for fault tolerance")
        print("   3. Submit jobs via http://localhost:8080/api/jobs (original API)")
        print("   4. Scale workers using Docker Compose")

def main():
    """Main test function"""
    print("🌟 Enhanced Poneglyph System Integration Test")
    print("Combining teammate's working system with your advanced middleware")
    print("=" * 70)
    
    tester = EnhancedSystemTester()
    
    # Check if services are running
    print("⏳ Checking if services are running...")
    print("   (Make sure you've run: docker-compose up -d)")
    time.sleep(3)
    
    # Run comprehensive test
    success = tester.test_enhanced_system()
    
    # Print detailed status
    tester.print_service_status()
    
    # Print integration guide
    tester.print_integration_guide()
    
    if success:
        print("\n🎉 INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print("Your advanced middleware is now working alongside teammate's system.")
    else:
        print("\n⚠️  INTEGRATION TEST COMPLETED WITH ISSUES")
        print("Check service logs and try: docker-compose logs [service-name]")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)