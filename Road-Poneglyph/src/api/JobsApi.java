package api;

import com.google.gson.Gson;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import core.Partitioner;
import core.Scheduler;
import http.HttpUtils;
import model.*;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Jobs endpoints grouped as nested handlers.
 */
public final class JobsApi {
    private JobsApi() {
    }

    private static final Gson gson = new Gson();

    /**
     * POST /api/jobs and GET /api/jobs (list ids)
     */
    public static class SubmitHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;
        private final Scheduler scheduler;

        public SubmitHandler(Map<String, JobCtx> jobs, Scheduler scheduler) {
            this.jobs = jobs;
            this.scheduler = scheduler;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            if ("POST".equals(ex.getRequestMethod())) {
                String body = HttpUtils.readBody(ex);
                JobSpec spec = gson.fromJson(body, JobSpec.class);

                JobCtx ctx = new JobCtx();
                ctx.spec = spec;
                ctx.mapScript = Base64.getDecoder().decode(spec.map_script_b64);
                ctx.reduceScript = Base64.getDecoder().decode(spec.reduce_script_b64);

                // init partitions
                for (int i = 0; i < spec.reducers; i++) ctx.partitionKV.put(i, new ArrayList<>());

                // build & enqueue maps
                int splitSize = Math.max(1, Optional.ofNullable(spec.split_size).orElse(1024));
                ctx.mapTasks = scheduler.buildMapTasks(spec.job_id, spec.input_text, splitSize);
                ctx.state = JobState.RUNNING;

                jobs.put(spec.job_id, ctx);
                scheduler.enqueueAll(ctx.mapTasks);

                HttpUtils.respondJson(ex, 200, Map.of("job_id", spec.job_id, "maps", ctx.mapTasks.size()));
                return;
            }
            if ("GET".equals(ex.getRequestMethod())) {
                HttpUtils.respondJson(ex, 200, jobs.keySet());
                return;
            }
            HttpUtils.respond(ex, 405, "", "");
        }
    }

    /**
     * GET /api/jobs/status?job_id=...
     */
    public static class StatusHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;

        public StatusHandler(Map<String, JobCtx> jobs) {
            this.jobs = jobs;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            String q = ex.getRequestURI().getQuery();
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "not found", "text/plain");
                return;
            }

            Map<String, Object> st = new LinkedHashMap<>();
            st.put("job_id", jobId);
            st.put("state", ctx.state.toString());
            st.put("maps_total", ctx.mapTasks.size());
            st.put("maps_completed", ctx.completedMaps);
            st.put("reduces_total", ctx.spec.reducers);
            st.put("reduces_completed", ctx.completedReduces);
            HttpUtils.respondJson(ex, 200, st);
        }
    }

    /**
     * GET /api/jobs/result?job_id=...
     */
    public static class ResultHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;

        public ResultHandler(Map<String, JobCtx> jobs) {
            this.jobs = jobs;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            String q = ex.getRequestURI().getQuery();
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "not found", "text/plain");
                return;
            }
            if (ctx.state != JobState.SUCCEEDED) {
                HttpUtils.respond(ex, 409, "not ready", "text/plain");
                return;
            }
            HttpUtils.respond(ex, 200, ctx.finalOutput, "text/plain");
        }
    }

    /**
     * GET /api/jobs/debug?job_id=...
     */
    public static class DebugHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;

        public DebugHandler(Map<String, JobCtx> jobs) {
            this.jobs = jobs;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            String q = ex.getRequestURI().getQuery();
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "not found", "text/plain");
                return;
            }

            List<Integer> parts = new ArrayList<>();
            for (int i = 0; i < ctx.spec.reducers; i++) parts.add(ctx.partitionKV.get(i).size());

            Map<String, Object> dbg = new LinkedHashMap<>();
            dbg.put("state", ctx.state.toString());
            dbg.put("partition_sizes", parts);
            HttpUtils.respondJson(ex, 200, dbg);
        }
    }

    /**
     * GET /api/jobs/scripts/{jobId}/{map.py|reduce.py}
     */
    public static class ScriptsHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;

        public ScriptsHandler(Map<String, JobCtx> jobs) {
            this.jobs = jobs;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            String path = ex.getRequestURI().getPath(); // /api/jobs/scripts/{jobId}/{which}
            String[] parts = path.split("/");
            if (parts.length != 6) {
                HttpUtils.respond(ex, 404, "", "");
                return;
            }
            String jobId = parts[4];
            String which = parts[5];

            JobCtx ctx = jobs.get(jobId);
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "", "");
                return;
            }
            byte[] data = "map.py".equals(which) ? ctx.mapScript : ctx.reduceScript;

            ex.getResponseHeaders().set("Content-Type", "text/x-python");
            ex.sendResponseHeaders(200, data.length);
            try (var os = ex.getResponseBody()) {
                os.write(data);
            }
        }
    }
}
