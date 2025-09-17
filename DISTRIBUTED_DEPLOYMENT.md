# 🌐 Distributed Poneglyph-Reduce Deployment Guide

This guide helps you deploy the Poneglyph-Reduce MapReduce cluster across **7 different machines** for a truly distributed setup.

## 📋 Machine Configuration

| Service       | Machine IP       | Script                | Purpose                           |
| ------------- | ---------------- | --------------------- | --------------------------------- |
| **Master**    | `107.21.170.137` | `deploy-master.sh`    | Job coordination, API, scheduling |
| **Worker 1**  | `54.221.98.28`   | `deploy-worker.sh`    | Map/Reduce task execution         |
| **Worker 2**  | `54.82.114.105`  | `deploy-worker.sh`    | Map/Reduce task execution         |
| **Worker 3**  | `3.89.106.235`   | `deploy-worker.sh`    | Map/Reduce task execution         |
| **Redis**     | `13.218.171.16`  | `deploy-redis.sh`     | Data storage, caching             |
| **EMQX**      | `54.146.208.48`  | `deploy-emqx.sh`      | MQTT broker, real-time messaging  |
| **Dashboard** | `13.222.179.191` | `deploy-dashboard.sh` | Web UI, monitoring                |

## 🚀 Quick Deployment Steps

### 1. Prepare All Machines

On **each machine**, run these commands to prepare the environment:

```bash
# Install Docker (if not already installed)
sudo apt update
sudo apt install docker.io docker-compose git -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Log out and back in for docker group changes
exit
# SSH back in
```

### 2. Deploy Services (Copy & Paste Scripts)

#### 🎯 Master Machine (107.21.170.137)

```bash
# Copy and paste the entire deploy-master.sh script content
# Then run:
chmod +x deploy-master.sh
./deploy-master.sh
```

#### 👷 Worker Machines (54.221.98.28, 54.82.114.105, 3.89.106.235)

```bash
# Copy and paste the entire deploy-worker.sh script content
# Then run:
chmod +x deploy-worker.sh
./deploy-worker.sh
```

#### 🗄️ Redis Machine (13.218.171.16)

```bash
# Copy and paste the entire deploy-redis.sh script content
# Then run:
chmod +x deploy-redis.sh
./deploy-redis.sh
```

#### 📡 EMQX Machine (54.146.208.48)

```bash
# Copy and paste the entire deploy-emqx.sh script content
# Then run:
chmod +x deploy-emqx.sh
./deploy-emqx.sh
```

#### 📊 Dashboard Machine (13.222.179.191)

```bash
# Copy and paste the entire deploy-dashboard.sh script content
# Then run:
chmod +x deploy-dashboard.sh
./deploy-dashboard.sh
```

## 🔧 Deployment Order

**Recommended deployment sequence:**

1. **Redis** (13.218.171.16) - Data storage foundation
2. **EMQX** (54.146.208.48) - Message broker
3. **Master** (107.21.170.137) - Central coordinator
4. **Workers** (54.221.98.28, 54.82.114.105, 3.89.106.235) - Task processors
5. **Dashboard** (13.222.179.191) - Monitoring UI

## 🌐 Network Access Points

After deployment, you can access:

- **🎯 Master API**: http://107.21.170.137:8080
- **📊 Dashboard**: http://13.222.179.191:3000
- **🗄️ RedisInsight**: http://13.218.171.16:5540
- **📡 EMQX Dashboard**: http://54.146.208.48:18083

## 🧪 Test Your Deployment

### 1. Test Master API

```bash
curl http://107.21.170.137:8080/api/health
```

### 2. Submit a Test Job

```bash
# On any machine with access to the master
curl -X POST http://107.21.170.137:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test-distributed-001",
    "map_script": "IyBNYXAgc2NyaXB0CmZvciBsaW5lIGluIG9wZW4oJ2lucHV0LnR4dCcpOgogICAgZm9yIHdvcmQgaW4gbGluZS5zdHJpcCgpLnNwbGl0KCk6CiAgICAgICAgcHJpbnQoZiJ7d29yZC5sb3dlcigpXQx0MSIp",
    "reduce_script": "IyBSZWR1Y2Ugc2NyaXB0CmltcG9ydCBzeXMKZGVmIG1haW4oKToKICAgIGt2ID0ge30KICAgIGZvciBsaW5lIGluIHN5cy5zdGRpbjoKICAgICAgICBpZiBsaW5lLnN0cmlwKCk6CiAgICAgICAgICAgIHdvcmQsIGNvdW50ID0gbGluZS5zdHJpcCgpLnNwbGl0KCdcdCcpCiAgICAgICAgICAgIGt2W3dvcmRdID0ga3Zbd29yZF0gKyBpbnQoY291bnQpIGlmIHdvcmQgaW4ga3YgZWxzZSBpbnQoY291bnQpCiAgICBmb3Igd29yZCwgY291bnQgaW4gc29ydGVkKGt2Lml0ZW1zKCkpOgogICAgICAgIHByaW50KGZ7e3dvcmR9fXx7Y291bnR9IikKbWFpbigp",
    "input_data": "b25lIGZpc2ggdHdvIGZpc2ggcmVkIGZpc2ggYmx1ZSBmaXNo",
    "split_size": 10,
    "reducers": 2
  }'
```

### 3. Check Job Status

```bash
curl "http://107.21.170.137:8080/api/jobs/status?job_id=test-distributed-001"
```

### 4. Get Results

```bash
curl "http://107.21.170.137:8080/api/jobs/result?job_id=test-distributed-001"
```

## 🔍 Monitoring & Troubleshooting

### Check Service Status

```bash
# On each machine
docker ps
docker compose ps
```

### View Logs

```bash
# Master logs
docker compose logs master

# Worker logs
docker compose logs worker

# Redis logs
docker compose logs redis

# EMQX logs
docker compose logs mqtt

# Dashboard logs
docker compose logs dashboard
```

### Network Connectivity Tests

```bash
# Test Redis connection from Master
redis-cli -h 13.218.171.16 -p 6379 ping

# Test MQTT connection
mosquitto_pub -h 54.146.208.48 -p 1883 -t test -m "hello"

# Test Master API from Workers
curl http://107.21.170.137:8080/api/health
```

## 🔧 Security Group Configuration

Ensure your EC2 security groups allow:

| Port  | Service        | Source                  | Purpose              |
| ----- | -------------- | ----------------------- | -------------------- |
| 22    | SSH            | Your IP                 | Management access    |
| 8080  | Master API     | All Workers + Dashboard | Job submission       |
| 50051 | Master gRPC    | All Workers             | Task assignment      |
| 6379  | Redis          | Master                  | Data storage         |
| 1883  | MQTT           | All Services            | Real-time messaging  |
| 8083  | MQTT WebSocket | Dashboard               | WebSocket connection |
| 3000  | Dashboard      | Your IP                 | Web UI access        |
| 18083 | EMQX Dashboard | Your IP                 | MQTT management      |
| 5540  | RedisInsight   | Your IP                 | Redis management     |

## 🎉 Success Indicators

Your distributed deployment is working when:

✅ **Master API responds**: `curl http://107.21.170.137:8080/api/health`  
✅ **Workers register**: Check master logs for worker registrations  
✅ **Dashboard loads**: http://13.222.179.191:3000 shows live data  
✅ **Jobs complete**: Test job runs successfully across workers  
✅ **Real-time updates**: Dashboard shows live job progress

## 🚀 Next Steps

1. **Scale Workers**: Add more worker machines using `deploy-worker.sh`
2. **Monitor Performance**: Use the dashboard and EMQX monitoring
3. **Configure AWS S3**: Update `.env` files with S3 credentials for persistent storage
4. **Set up Load Balancing**: Use AWS Application Load Balancer for high availability

---

**🌟 Congratulations!** You now have a fully distributed MapReduce cluster running across 7 machines! 🎊
