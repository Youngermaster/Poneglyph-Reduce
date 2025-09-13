# Poneglyph-Reduce

Sistema distribuido de Map-Reduce con middleware avanzado para procesamiento de datos en la nube, con tolerancia a fallos, balanceador de carga inteligente y monitoreo en tiempo real.

## 🚀 Características Principales

- **🛡️ Fault Tolerance**: Sistema completo de tolerancia a fallos con circuit breakers, retry logic y dead letter queue
- **⚖️ Load Balancing**: Balanceador de carga inteligente con múltiples estrategias y métricas de rendimiento
- **📊 Monitoring**: Monitoreo en tiempo real con métricas de Prometheus y APIs HTTP
- **🌐 Multi-Protocol**: Soporte para gRPC, HTTP REST APIs y MQTT
- **☁️ Cloud Ready**: Integración con AWS (S3, DynamoDB) y contenedores Docker
- **🔄 Auto-Recovery**: Recuperación automática de tareas fallidas y workers problemáticos

## 📁 Estructura del Proyecto

```
Poneglyph-Reduce/
├── middleware/                 # Core middleware components
│   ├── config.py              # Configuración centralizada
│   ├── server.py              # Servidor principal
│   ├── grpc_middleware.py     # Servicios gRPC base
│   ├── fault_tolerance.py     # Sistema de tolerancia a fallos
│   ├── fault_tolerant_grpc.py # Servicios gRPC con fault tolerance
│   ├── fault_tolerance_api.py # API HTTP para gestión
│   ├── load_balancer.py       # Balanceador de carga inteligente
│   ├── metrics_collector.py   # Recolección de métricas
│   ├── metrics_server.py      # Servidor HTTP de métricas
│   ├── state_store.py         # Almacenamiento de estado en memoria
│   ├── dynamodb_state_store.py# Almacenamiento en DynamoDB
│   ├── mqtt_bridge.py         # Bridge MQTT para comunicación
│   └── generated/             # Archivos protobuf generados
├── tests/                     # Pruebas y demostraciones
│   ├── test_fault_tolerance_simplified.py
│   └── production_fault_tolerance_demo.py
├── docs/                      # Documentación
│   ├── FAULT_TOLERANCE_SUMMARY.md
│   └── ARQUITECTURA_FINAL.md
├── aws-native/                # Implementaciones nativas AWS
├── Clover/                    # Clientes de prueba
├── Poneglyph/                 # Workers C++
├── Road-Poneglyph/           # Implementación Java/Spring
└── requirements.txt          # Dependencias Python
```

## 🛠️ Instalación y Configuración

### Prerrequisitos

- Python 3.8+
- Node.js 16+ (opcional, para workers JavaScript)
- Java 11+ (opcional, para componentes Java)
- Docker (opcional, para despliegue en contenedores)

### Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/Youngermaster/Poneglyph-Reduce.git
   cd Poneglyph-Reduce
   ```

2. **Crear entorno virtual:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate     # Windows PowerShell
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno (opcional):**
   ```powershell
   $env:PONEGLYPH_GRPC_PORT="50051"
   $env:PONEGLYPH_METRICS_PORT="8080"
   $env:PONEGLYPH_FT_API_PORT="8083"
   $env:PONEGLYPH_USE_DYNAMODB="false"
   ```

## 🚀 Ejecución

### Servidor Principal

Ejecutar el servidor completo con todas las características:

```powershell
cd middleware
python server.py
```

Esto iniciará:
- 📡 **gRPC Server**: `localhost:50051`
- 📊 **Metrics API**: `http://localhost:8080`
- 🛡️ **Fault Tolerance API**: `http://localhost:8083`
- 📋 **Dashboard**: `http://localhost:8083/fault-tolerance/dashboard`

### Modo de Desarrollo

Para pruebas y desarrollo, puedes usar el servidor legacy:

```powershell
python middleware/grpc_middleware.py
```

## 🧪 Pruebas y Demos

### Test Suite Simplificado

Ejecutar las pruebas del sistema de fault tolerance:

```powershell
python tests/test_fault_tolerance_simplified.py
```

### Demo de Producción

Ejecutar una simulación realista con chaos engineering:

```powershell
python tests/production_fault_tolerance_demo.py
```

Este demo simula:
- ✅ 8 workers con diferentes perfiles de rendimiento
- 💥 Fallos aleatorios y crashes de workers
- 🔄 Retry automático y circuit breakers
- 📊 Métricas en tiempo real
- 🎯 90 tareas procesadas en 2 minutos

## 📊 Monitoring y APIs

### Métricas de Prometheus

```powershell
curl http://localhost:8080/metrics
```

### API de Fault Tolerance

```powershell
# Estadísticas generales
curl http://localhost:8083/fault-tolerance/stats

# Estado de circuit breakers
curl http://localhost:8083/fault-tolerance/circuit-breakers

# Dashboard completo
curl http://localhost:8083/fault-tolerance/dashboard

# Recuperar tarea de dead letter queue
curl -X POST http://localhost:8083/fault-tolerance/dead-letter-queue/{task_id}/recover
```

## 🛡️ Características de Fault Tolerance

### Circuit Breakers
- **Estados**: CLOSED → OPEN → HALF_OPEN → CLOSED
- **Threshold**: 5 fallos consecutivos
- **Recovery**: 60 segundos timeout
- **Auto-recovery**: Tras 3 llamadas exitosas

### Retry Logic
- **Max retries**: 3 por defecto
- **Exponential backoff**: `base_delay * (2.0 ^ attempt)`
- **Jitter**: ±20% para evitar thundering herd
- **Smart retry**: Reasignación automática a workers sanos

### Dead Letter Queue
- **Capacidad**: 1000 tareas por defecto
- **Recovery manual**: Via API HTTP
- **Análisis**: Razones de fallo categorizadas

## ⚖️ Load Balancing

### Estrategias Disponibles

1. **Round Robin**: Distribución secuencial
2. **Least Connections**: Menos conexiones activas
3. **Capacity Aware**: Basado en capacidad del worker
4. **Health Based**: Considerando salud del worker
5. **Smart Composite**: Algoritmo inteligente (recomendado)

### Métricas Consideradas

- **Availability**: Disponibilidad del worker (30%)
- **Health**: Estado de salud (25%)
- **Efficiency**: Eficiencia de procesamiento (25%)
- **Reliability**: Confiabilidad histórica (20%)
- **Capacity Penalty**: Penalización por saturación

## 🌐 Integración Cloud

### AWS Integration

```powershell
# Configurar DynamoDB
$env:PONEGLYPH_USE_DYNAMODB="true"
$env:AWS_REGION="us-east-1"
$env:PONEGLYPH_DYNAMODB_TABLE="poneglyph-state"

# Configurar S3
$env:S3_BUCKET="my-poneglyph-bucket"
```

### Docker Support

```powershell
# Build
docker build -t poneglyph-middleware .

# Run
docker run -p 50051:50051 -p 8080:8080 -p 8083:8083 poneglyph-middleware
```

## 🔧 Configuración Avanzada

### Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PONEGLYPH_GRPC_PORT` | 50051 | Puerto gRPC |
| `PONEGLYPH_METRICS_PORT` | 8080 | Puerto métricas HTTP |
| `PONEGLYPH_FT_API_PORT` | 8083 | Puerto API fault tolerance |
| `PONEGLYPH_TASK_TIMEOUT` | 300 | Timeout tareas (segundos) |
| `PONEGLYPH_MAX_RETRIES` | 3 | Máximo reintentos |
| `PONEGLYPH_USE_DYNAMODB` | false | Usar DynamoDB |
| `PONEGLYPH_MQTT_BROKER` | localhost | Broker MQTT |

### Configuración Programática

```python
from middleware.config import get_config

config = get_config()
config.set("DEFAULT_TASK_TIMEOUT", 600)  # 10 minutes
config.set("MAX_RETRIES", 5)
```

## 📈 Métricas y KPIs

### Métricas Clave

- **Success Rate**: Tasa de éxito general
- **Task Throughput**: Tareas procesadas por minuto
- **Worker Health**: Estado de salud de workers
- **Circuit Breaker Status**: Estado de circuit breakers
- **Retry Rate**: Tasa de reintentos
- **Dead Letter Rate**: Tareas en dead letter queue

### Dashboard

Acceder al dashboard web completo:
`http://localhost:8083/fault-tolerance/dashboard`

## 🤝 Contribución

1. Fork el repositorio
2. Crear branch feature (`git checkout -b feature/amazing-feature`)
3. Commit cambios (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Abrir Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para detalles.

## 🏆 Estado del Proyecto

✅ **Sistema de Fault Tolerance**: Completado y validado  
✅ **Load Balancing Inteligente**: Completado y validado  
✅ **Monitoring en Tiempo Real**: Completado y validado  
✅ **APIs HTTP Completas**: Completado y validado  
✅ **Testing Exhaustivo**: Completado y validado  
✅ **Documentación**: Completado y actualizado  

**Estado Actual**: 🎉 **PRODUCTION READY**

---

*Desarrollado con ❤️ para procesamiento distribuido de datos*