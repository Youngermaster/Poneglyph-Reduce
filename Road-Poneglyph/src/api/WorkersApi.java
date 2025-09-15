package api;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import http.HttpUtils;
import model.Worker;
import store.RedisStore;
import telemetry.MqttClientManager;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;

public final class WorkersApi {
    private WorkersApi() {}

    /**
     * POST /api/workers/register
     */
    public static class RegisterHandler implements HttpHandler {
        private final Map<String, Worker> workers;
        private final MqttClientManager mqtt;
        private final RedisStore redis;

        public RegisterHandler(Map<String, Worker> workers, MqttClientManager mqtt, RedisStore redis) {
            this.workers = workers;
            this.mqtt = mqtt;
            this.redis = redis;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            if (!"POST".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }
            String body = HttpUtils.readBody(ex);
            JsonObject j = JsonParser.parseString(body).getAsJsonObject();

            Worker w = new Worker();
            w.workerId = "w-" + UUID.randomUUID();
            w.name = j.has("name") ? j.get("name").getAsString() : w.workerId;
            w.capacity = j.has("capacity") ? j.get("capacity").getAsInt() : 1;
            
            // Inicializar métricas del sistema si están disponibles
            if (j.has("cpu_usage")) {
                w.cpuUsage = j.get("cpu_usage").getAsDouble();
            }
            if (j.has("memory_usage")) {
                w.memoryUsage = j.get("memory_usage").getAsDouble();
            }
            
            w.lastHeartbeat = System.currentTimeMillis();

            workers.put(w.workerId, w);

            if (redis != null) redis.saveWorker(w);
            if (mqtt != null) mqtt.publishJson("gridmr/worker/registered", Map.of(
                    "workerId", w.workerId, "name", w.name, "capacity", w.capacity, "ts", System.currentTimeMillis()
            ));

            HttpUtils.respondJson(ex, 200, Map.of("worker_id", w.workerId, "poll_interval_ms", 1000));
        }
    }

    /**
     * POST /api/workers/heartbeat - Workers reportan métricas y mantienen conexión
     */
    public static class HeartbeatHandler implements HttpHandler {
        private final Map<String, Worker> workers;
        private final MqttClientManager mqtt;

        public HeartbeatHandler(Map<String, Worker> workers, MqttClientManager mqtt) {
            this.workers = workers;
            this.mqtt = mqtt;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            if (!"POST".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }
            
            String body = HttpUtils.readBody(ex);
            JsonObject j = JsonParser.parseString(body).getAsJsonObject();
            
            String workerId = j.get("worker_id").getAsString();
            Worker worker = workers.get(workerId);
            
            if (worker == null) {
                HttpUtils.respond(ex, 404, "Worker not found", "text/plain");
                return;
            }
            
            // Actualizar heartbeat
            worker.lastHeartbeat = System.currentTimeMillis();
            
            // Actualizar métricas de sistema si están disponibles
            if (j.has("cpu_usage")) {
                worker.cpuUsage = Math.max(0.0, Math.min(1.0, j.get("cpu_usage").getAsDouble()));
            }
            if (j.has("memory_usage")) {
                worker.memoryUsage = Math.max(0.0, Math.min(1.0, j.get("memory_usage").getAsDouble()));
            }
            
            // Publicar métricas via MQTT
            if (mqtt != null) {
                mqtt.publishJson("gridmr/worker/heartbeat", Map.of(
                    "workerId", workerId,
                    "cpuUsage", worker.cpuUsage,
                    "memoryUsage", worker.memoryUsage,
                    "activeTasks", worker.activeTasks,
                    "capacity", worker.capacity,
                    "loadScore", worker.getLoadScore(),
                    "ts", System.currentTimeMillis()
                ));
            }
            
            HttpUtils.respondJson(ex, 200, Map.of("status", "ok"));
        }
    }
}
