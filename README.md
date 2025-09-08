# Poneglyph-Reduce: Distributed MapReduce System with gRPC Middleware

A high-performance distributed MapReduce system implementing the framework from the classic Google MapReduce paper, enhanced with modern gRPC middleware for efficient communication and job orchestration.

## 🏗️ Architecture

```
┌─────────────────┐    gRPC     ┌──────────────────┐    RabbitMQ    ┌─────────────────┐
│   Java Master   │◄────────────│  gRPC Middleware │◄───────────────│  C++ Workers    │
│   (Scheduler)   │             │   (Python)       │               │  (Map/Reduce)   │
└─────────────────┘             └──────────────────┘               └─────────────────┘
                                          │
                                     Redis │
                                          ▼
                                ┌──────────────────┐
                                │  Distributed     │
                                │  State Store     │
                                └──────────────────┘
```

### Core Components

- **Java Master** (`Road-Poneglyph/`): Job scheduler and coordinator with HTTP REST API
- **C++ Workers** (`Poneglyph/`): High-performance MAP/REDUCE task processors  
- **gRPC Middleware** (`PoneglyphMiddleware/`): Modern communication layer with RabbitMQ + Redis
- **Docker Orchestration**: Containerized deployment with docker-compose

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- Java 17+ (for master development)
- CMake & GCC (for worker development)

### Basic System (HTTP)
```bash
# Start basic MapReduce system
docker-compose -f docker-compose.basic.yml up -d

# Test with sample job
curl -X POST http://localhost:8080/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test_job",
    "input_data": "one fish two fish red fish blue fish",
    "map_script": "#!/usr/bin/env python3\nimport sys\nfor line in sys.stdin:\n    for word in line.split():\n        print(f\"{word}\\t1\")",
    "reduce_script": "#!/usr/bin/env python3\nimport sys\ncurrent_word = None\ncurrent_count = 0\nfor line in sys.stdin:\n    word, count = line.strip().split(\"\\t\")\n    if current_word == word:\n        current_count += int(count)\n    else:\n        if current_word:\n            print(f\"{current_word}\\t{current_count}\")\n        current_word = word\n        current_count = int(count)\nif current_word:\n    print(f\"{current_word}\\t{current_count}\")"
  }'

# Check job status
curl http://localhost:8080/api/jobs/status?job_id=test_job
```

### gRPC System (Advanced)
```bash
# Start gRPC infrastructure  
docker-compose -f docker-compose.grpc.yml up rabbitmq redis -d

# Run gRPC middleware locally
cd PoneglyphMiddleware
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python grpc_middleware.py

# Test gRPC client
python test_grpc_client.py
```

## 📚 System Details

### HTTP API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/jobs` | POST | Submit MapReduce job |
| `/api/jobs/status` | GET | Get job status |

### gRPC Services

| Service | Methods | Description |
|---------|---------|-------------|
| `JobManagementService` | `SubmitJob`, `GetJobStatus` | Job lifecycle management |
| `WorkerManagementService` | `RegisterWorker`, `SendHeartbeat` | Worker coordination |
| `TaskDistributionService` | `RequestTask`, `CompleteTask` | Task assignment and completion |

### Job Execution Flow

1. **Job Submission**: Client submits job with MAP/REDUCE scripts
2. **Task Creation**: Master splits input data into MAP tasks
3. **Worker Registration**: C++ workers register with middleware  
4. **Task Distribution**: Middleware assigns tasks via RabbitMQ
5. **MAP Phase**: Workers process input chunks and emit key-value pairs
6. **REDUCE Phase**: Workers aggregate results by key
7. **Result Collection**: Final results stored in Redis/returned to client

## 🔧 Development

### Adding New Features

1. **gRPC Protocol Changes**: Modify `poneglyph.proto`, regenerate with:
   ```bash
   python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. poneglyph.proto
   ```

2. **Master Extensions**: Enhance Java REST API in `Road-Poneglyph/src/Main.java`

3. **Worker Optimization**: Improve C++ performance in `Poneglyph/main.cpp`

4. **Middleware Logic**: Extend Python gRPC services in `grpc_middleware.py`

### Testing

```bash
# Basic system test
docker-compose -f docker-compose.basic.yml up -d
# Run your test jobs...

# gRPC system test  
cd PoneglyphMiddleware
python test_grpc_client.py
```

## 📊 Performance Features

- **Horizontal Scaling**: Add more workers by scaling Docker containers
- **Fault Tolerance**: Worker failure detection and task reassignment
- **Load Balancing**: Intelligent task distribution via middleware
- **Efficient Communication**: gRPC binary protocol vs HTTP JSON
- **Persistent Storage**: Redis for job state and RabbitMQ for message queuing

## 🐳 Docker Configuration

### Basic System
```yaml
# docker-compose.basic.yml
services:
  master:    # Java scheduler on port 8080
  worker-1:  # C++ MAP/REDUCE processor
  worker-2:  # C++ MAP/REDUCE processor  
  minio:     # S3-compatible storage
```

### gRPC System
```yaml
# docker-compose.grpc.yml  
services:
  grpc-middleware: # Python gRPC server on port 50051
  rabbitmq:        # Message queue on port 5672
  redis:           # State store on port 6379
```

## 🎯 Use Cases

- **Data Processing**: Large-scale text analysis, log processing
- **Machine Learning**: Distributed feature extraction, model training
- **Analytics**: Batch processing of business metrics
- **Research**: Academic distributed systems experiments

## 📝 Implementation Notes

- **Language Choice**: Java for reliability, C++ for performance, Python for middleware agility
- **Communication**: HTTP for simplicity, gRPC for high-performance scenarios
- **Storage**: MinIO (S3-compatible) for job data, Redis for fast state access
- **Messaging**: RabbitMQ for reliable task distribution and result collection

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 References

- [MapReduce: Simplified Data Processing on Large Clusters](https://research.google.com/archive/mapreduce.html)
- [gRPC Documentation](https://grpc.io/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)

---

**Built with ❤️ for distributed systems education and high-performance computing.**
