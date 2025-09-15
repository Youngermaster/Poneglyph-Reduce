#!/bin/bash

echo "🚀 Testing Smart Scheduler Implementation"
echo "========================================"

# Build and start the system
echo "Building and starting the system..."
docker-compose up --build --scale worker=3 -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "📊 Checking scheduler stats:"
curl -s "http://localhost:8080/api/scheduler/stats" | jq .

echo ""
echo "🏥 Checking health endpoints:"
echo "Master Health:"
curl -s "http://localhost:8080/api/health"
echo ""
echo "MQTT Health:"
curl -s "http://localhost:8080/api/health/mqtt"
echo ""
echo "Redis Health:"
curl -s "http://localhost:8080/api/health/redis"
echo ""

echo ""
echo "🎯 Submitting test job via client..."
docker-compose run --rm client

echo ""
echo "📈 Final scheduler stats:"
curl -s "http://localhost:8080/api/scheduler/stats" | jq .

echo ""
echo "✅ Test completed! Check dashboard at http://localhost:3000"