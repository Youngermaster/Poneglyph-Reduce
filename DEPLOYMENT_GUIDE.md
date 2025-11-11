# Poneglyph MapReduce - Guía de Despliegue Distribuido

## 📋 Resumen de Configuración

### Infraestructura AWS

- **Master (Road-Poneglyph)**: `35.153.249.132`
- **Workers**: `98.87.213.90`, `98.88.24.152`, `54.145.27.176`
- **MQTT Broker (EMQX)**: `50.16.155.173`
- **Dashboard**: `54.237.114.35`

## 🚀 Comandos de Despliegue por Servicio

### 1. Master (Road-Poneglyph) - `35.153.249.132`

```bash
# Copiar archivos
scp -i "GridMR-KeyFile.pem" -r Road-Poneglyph/ ubuntu@35.153.249.132:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" docker-compose.yml ubuntu@35.153.249.132:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" .env ubuntu@35.153.249.132:/opt/Poneglyph-Reduce/

# SSH y despliegue
ssh -i "GridMR-KeyFile.pem" ubuntu@35.153.249.132
cd /opt/Poneglyph-Reduce
docker compose up redis redisinsight --build -d
```

### 2. Workers - `98.87.213.90`, `98.88.24.152`, `54.145.27.176`

```bash
# Copiar archivos (repetir para cada worker)
scp -i "GridMR-KeyFile.pem" -r Poneglyph/ ubuntu@[WORKER_IP]:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" docker-compose.yml ubuntu@[WORKER_IP]:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" .env ubuntu@[WORKER_IP]:/opt/Poneglyph-Reduce/

# SSH y despliegue (en cada worker)
ssh -i "GridMR-KeyFile.pem" ubuntu@[WORKER_IP]
cd /opt/Poneglyph-Reduce
docker compose up -d worker
```

### 3. MQTT Broker (EMQX) - `50.16.155.173`

```bash
# Copiar archivos
scp -i "GridMR-KeyFile.pem" docker-compose.yml ubuntu@50.16.155.173:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" .env ubuntu@50.16.155.173:/opt/Poneglyph-Reduce/

# SSH y despliegue
ssh -i "GridMR-KeyFile.pem" ubuntu@50.16.155.173
cd /opt/Poneglyph-Reduce
docker compose up -d mqtt
```

### 4. Dashboard - `54.237.114.35`

```bash
# Copiar archivos
scp -i "GridMR-KeyFile.pem" -r dashboard/ ubuntu@54.237.114.35:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" docker-compose.yml ubuntu@54.237.114.35:/opt/Poneglyph-Reduce/
scp -i "GridMR-KeyFile.pem" .env ubuntu@54.237.114.35:/opt/Poneglyph-Reduce/

# SSH y despliegue
ssh -i "GridMR-KeyFile.pem" ubuntu@54.237.114.35
cd /opt/Poneglyph-Reduce
docker compose build --no-cache dashboard
docker compose up -d dashboard
```

## ⚙️ Configuraciones Críticas

### Archivo `.env` Principal

```env
# AWS S3 Configuration
AWS_S3_BUCKET=poneglyph
AWS_S3_BASE_PATH=results/
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=ASIAZI2LDTJP37LVJPSG
AWS_SECRET_ACCESS_KEY=oNleYaongx+KAcUw2XQrzYfdBXIVdgkqb1YNjgA8
AWS_SESSION_TOKEN=IQoJb3JpZ2luX2VjEE0a...
# MQTT Configuration
MQTT_USERNAME=admin
MQTT_PASSWORD=public
MQTT_PORT=1883
MQTT_WS_PORT=8083
MQTT_DASHBOARD_PORT=18083
# Master/API Configuration
MASTER_HTTP_PORT=8080
MASTER_GRPC_PORT=50051
MASTER_API_URL=http://35.153.249.132:8080
# Redis Configuration
REDIS_PORT=6379
# Dashboard Configuration
DASHBOARD_PORT=3000
DASHBOARD_INTERNAL_PORT=5173
VITE_MQTT_HOST=50.16.155.173
VITE_MQTT_PORT=8083
VITE_MASTER_API=http://35.153.249.132:8080
# RedisInsight Configuration
REDISINSIGHT_PORT=5540
# Docker Container Names
MASTER_CONTAINER_NAME=road-poneglyph
DASHBOARD_CONTAINER_NAME=dashboard
MQTT_CONTAINER_NAME=emqx
REDIS_CONTAINER_NAME=redis
REDISINSIGHT_CONTAINER_NAME=redisinsight
```

### Dashboard - Configuración MQTT Corregida

```bash
# Archivo: /opt/Poneglyph-Reduce/dashboard/src/hooks/useMqtt.ts
# Cambio realizado:
sed -i 's/34.235.115.144/50.16.155.173/g' /opt/Poneglyph-Reduce/dashboard/src/hooks/useMqtt.ts

# Archivo: /opt/Poneglyph-Reduce/dashboard/.env
echo "VITE_MQTT_HOST=50.16.155.173" > /opt/Poneglyph-Reduce/dashboard/.env
echo "VITE_MQTT_PORT=8083" >> /opt/Poneglyph-Reduce/dashboard/.env
```

## 🔧 Comandos de Mantenimiento

### Verificar Estado de Servicios

```bash
# Master
ssh -i "GridMR-KeyFile.pem" ubuntu@35.153.249.132 "docker ps && docker logs road-poneglyph --tail 10"

# Workers
ssh -i "GridMR-KeyFile.pem" ubuntu@98.87.213.90 "docker ps && docker logs worker --tail 10"
ssh -i "GridMR-KeyFile.pem" ubuntu@98.88.24.152 "docker ps && docker logs worker --tail 10"
ssh -i "GridMR-KeyFile.pem" ubuntu@54.145.27.176 "docker ps && docker logs worker --tail 10"

# MQTT Broker
ssh -i "GridMR-KeyFile.pem" ubuntu@50.16.155.173 "docker ps && docker logs emqx --tail 10"

# Dashboard
ssh -i "GridMR-KeyFile.pem" ubuntu@54.237.114.35 "docker ps && docker logs dashboard --tail 10"
```

### Reiniciar Servicios

```bash
# Reiniciar Master
ssh -i "GridMR-KeyFile.pem" ubuntu@35.153.249.132 "cd /opt/Poneglyph-Reduce && docker compose restart master"

# Reiniciar Worker
ssh -i "GridMR-KeyFile.pem" ubuntu@[WORKER_IP] "cd /opt/Poneglyph-Reduce && docker compose restart worker"

# Reiniciar Dashboard (con rebuild si hay cambios de configuración)
ssh -i "GridMR-KeyFile.pem" ubuntu@54.237.114.35 "cd /opt/Poneglyph-Reduce && docker compose build --no-cache dashboard && docker compose restart dashboard"
```

## 🧪 Comandos de Prueba

### Verificar Conectividad MQTT

```bash
# Suscribirse a mensajes de telemetría
ssh -i "GridMR-KeyFile.pem" ubuntu@54.237.114.35 "timeout 5 mosquitto_sub -h 50.16.155.173 -p 1883 -t 'gridmr/#'"
```

### Ejecutar Trabajos MapReduce desde Cliente Local

```bash
# Configurar variable de entorno y ejecutar
cd "C:\Users\sebas\Documents\Eafit\Semestre 10\Telemática\Poneglyph-Reduce\Clover"
$env:MASTER="http://35.153.249.132:8080"
python submit_job_enhanced.py examples/monte-carlo
python submit_job_enhanced.py examples/regresion-lineal
python submit_job_enhanced.py examples/automatas-celulares
python submit_job_enhanced.py examples/ciencia-datos
```

## 🌐 URLs de Acceso

- **Dashboard**: http://54.237.114.35:3000
- **Master API**: http://35.153.249.132:8080
- **EMQX Dashboard**: http://50.16.155.173:18083 (admin/public)
- **RedisInsight**: http://35.153.249.132:5540

## ✅ Estado Final del Sistema

- ✅ Master ejecutándose con API REST y gRPC
- ✅ 3 Workers activos enviando telemetría
- ✅ MQTT Broker recibiendo mensajes de workers
- ✅ Dashboard conectado mostrando métricas en tiempo real
- ✅ Redis persistiendo datos
- ✅ Cliente local ejecutando trabajos remotos exitosamente

## 🔑 Cambios Críticos Realizados

1. **Dashboard MQTT**: Corregir IP de `34.235.115.144` a `50.16.155.173`
2. **Variables de entorno**: Configurar `VITE_MQTT_HOST` y `VITE_MQTT_PORT`
3. **Dockerfile optimizado**: Usar `Dockerfile.prebuilt` para workers
4. **Cliente mejorado**: Crear `submit_job_enhanced.py` para ejemplos específicos

El sistema está completamente operacional y monitoreando trabajos MapReduce distribuidos en tiempo real.
