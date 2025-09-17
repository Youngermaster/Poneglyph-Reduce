#!/bin/bash

# ===========================================
# PONEGLYPH-REDUCE REDIS DEPLOYMENT
# Machine: 13.218.171.16
# ===========================================

echo "🚀 Deploying Poneglyph-Reduce Redis on $(hostname)"
echo "=============================================="

# Clone repository if not exists
if [ ! -d "Poneglyph-Reduce" ]; then
    echo "📂 Cloning repository..."
    git clone https://github.com/Youngermaster/Poneglyph-Reduce.git
fi

cd Poneglyph-Reduce

# Create environment file for redis
cat > .env << 'EOF'
# Master Configuration
MASTER_CONTAINER_NAME=poneglyph-master
MASTER_HTTP_PORT=8080
MASTER_GRPC_PORT=50051
MASTER_API_URL=http://107.21.170.137:8080

# Worker Configuration
WORKER_CONTAINER_NAME=poneglyph-worker

# Redis Configuration
REDIS_CONTAINER_NAME=poneglyph-redis
REDIS_PORT=6379
REDIS_URL=redis://13.218.171.16:6379

# EMQX Configuration
MQTT_CONTAINER_NAME=poneglyph-mqtt
MQTT_PORT=1883
MQTT_WS_PORT=8083
MQTT_DASHBOARD_PORT=18083
MQTT_USERNAME=admin
MQTT_PASSWORD=password123
MQTT_BROKER=tcp://54.146.208.48:1883

# Dashboard Configuration
DASHBOARD_CONTAINER_NAME=poneglyph-dashboard
DASHBOARD_PORT=3000
DASHBOARD_INTERNAL_PORT=3000
VITE_MQTT_HOST=54.146.208.48
VITE_MQTT_PORT=8083
VITE_MASTER_API=http://107.21.170.137:8080

# RedisInsight Configuration
REDISINSIGHT_CONTAINER_NAME=poneglyph-redisinsight
REDISINSIGHT_PORT=5540

# AWS S3 Configuration (optional)
AWS_S3_BUCKET=
AWS_S3_BASE_PATH=
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
EOF

echo "🔧 Building and starting Redis services..."
docker compose up redis redisinsight --build -d

echo "✅ Redis deployment complete!"
echo ""
echo "📋 Redis services running:"
echo "  - Redis: 13.218.171.16:6379"
echo "  - RedisInsight: http://13.218.171.16:5540"
echo ""
echo "🔍 Check logs: docker compose logs redis"
echo "🌐 Test Redis: redis-cli -h 13.218.171.16 -p 6379 ping"
echo "📊 Monitor: docker stats redis"
