package api;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import http.HttpUtils;
import model.Worker;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;

public final class WorkersApi {
    private WorkersApi() {
    }

    /**
     * POST /api/workers/register
     */
    public static class RegisterHandler implements HttpHandler {
        private final Map<String, Worker> workers;

        public RegisterHandler(Map<String, Worker> workers) {
            this.workers = workers;
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

            workers.put(w.workerId, w);
            HttpUtils.respondJson(ex, 200, Map.of(
                    "worker_id", w.workerId,
                    "poll_interval_ms", 1000
            ));
        }
    }
}
