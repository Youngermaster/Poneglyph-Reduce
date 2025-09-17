#!/bin/bash

# ===========================================
# PONEGLYPH-REDUCE MASTER DEPLOYMENT
# Machine: 107.21.170.137
# ===========================================

echo "🚀 Deploying Poneglyph-Reduce Master on $(hostname)"
echo "=============================================="

# Clone repository if not exists
if [ ! -d "Poneglyph-Reduce" ]; then
    echo "📂 Cloning repository..."
    git clone https://github.com/Youngermaster/Poneglyph-Reduce.git
fi

cd Poneglyph-Reduce

# Create environment file for master
cat > .env << 'EOF'
# Master Configuration
MASTER_CONTAINER_NAME=poneglyph-master
MASTER_HTTP_PORT=8080
MASTER_GRPC_PORT=50051
MASTER_API_URL=http://107.21.170.137:8080

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

echo "🔧 Building and starting Master services..."
docker compose up master redis redisinsight --build -d

echo "✅ Master deployment complete!"
echo ""
echo "📋 Master services running:"
echo "  - Master API: http://107.21.170.137:8080"
echo "  - Redis: 13.218.171.16:6379"
echo "  - RedisInsight: http://107.21.170.137:5540"
echo ""
echo "🔍 Check logs: docker compose logs master"
echo "🌐 Test API: curl http://107.21.170.137:8080/api/health"
