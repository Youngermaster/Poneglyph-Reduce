import com.google.gson.*;
import com.sun.net.httpserver.*;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * Road-Poneglyph: Master HTTP server (v1)
 * - Job submit
 * - Worker register & task polling
 * - Map/Shuffle on master, Reduce on workers
 */
public class Main {

    // ----- Models -----
    enum TaskType {MAP, REDUCE}

    enum JobState {PENDING, RUNNING, SUCCEEDED, FAILED}

    static class JobSpec {
        String job_id;
        String input_text;
        Integer split_size;
        Integer reducers;
        String format;
        String map_script_b64;
        String reduce_script_b64;
    }

    static class Worker {
        String workerId;
        String name;
        int capacity;
        long lastHeartbeat = System.currentTimeMillis();
    }

    static class Task {
        String taskId;
        String jobId;
        TaskType type;
        // MAP
        String inputChunk;
        // REDUCE
        int partitionIndex;
        List<String> kvLinesForReduce = new ArrayList<>();
    }

    static class JobCtx {
        JobSpec spec;
        JobState state = JobState.PENDING;
        List<Task> mapTasks = new ArrayList<>();
        Map<Integer, List<String>> partitionKV = new HashMap<>(); // reducerIndex -> lines "k\tv"
        List<Task> reduceTasks = new ArrayList<>();
        String finalOutput = "";
        byte[] mapScript;    // raw py
        byte[] reduceScript; // raw py
        int completedMaps = 0;
        int completedReduces = 0;
    }

    // ----- State (in-memory) -----
    static final Gson gson = new GsonBuilder().create();
    static final Map<String, Worker> workers = new ConcurrentHashMap<>();
    static final Map<String, JobCtx> jobs = new ConcurrentHashMap<>();
    static final BlockingQueue<Task> pendingTasks = new LinkedBlockingQueue<>();

    // ----- Utils -----
    static String readBody(HttpExchange ex) throws IOException {
        try (InputStream is = ex.getRequestBody()) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    static void respond(HttpExchange ex, int code, String body, String contentType) throws IOException {
        byte[] bytes = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().add("Content-Type", contentType);
        ex.sendResponseHeaders(code, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }

    static void respondJson(HttpExchange ex, int code, Object obj) throws IOException {
        respond(ex, code, gson.toJson(obj), "application/json");
    }

    static int partitionOf(String key, int reducers) {
        return Math.floorMod(key.hashCode(), reducers);
    }

    // ----- Server -----
    public static void main(String[] args) throws Exception {
        int port = 8080;
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        // Health
        server.createContext("/api/health", ex -> {
            respond(ex, 200, "OK", "text/plain");
        });

        // Register worker
        server.createContext("/api/workers/register", ex -> {
            if (!"POST".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            String body = readBody(ex);
            JsonObject j = JsonParser.parseString(body).getAsJsonObject();
            Worker w = new Worker();
            w.workerId = "w-" + UUID.randomUUID();
            w.name = j.has("name") ? j.get("name").getAsString() : w.workerId;
            w.capacity = j.has("capacity") ? j.get("capacity").getAsInt() : 1;
            workers.put(w.workerId, w);
            Map<String, Object> resp = Map.of("worker_id", w.workerId, "poll_interval_ms", 1000);
            respondJson(ex, 200, resp);
        });

        // Submit job
        server.createContext("/api/jobs", ex -> {
            if ("POST".equals(ex.getRequestMethod())) {
                String body = readBody(ex);
                JobSpec spec = gson.fromJson(body, JobSpec.class);
                JobCtx ctx = new JobCtx();
                ctx.spec = spec;
                ctx.mapScript = Base64.getDecoder().decode(spec.map_script_b64);
                ctx.reduceScript = Base64.getDecoder().decode(spec.reduce_script_b64);
                ctx.partitionKV = new HashMap<>();
                for (int i = 0; i < spec.reducers; i++) ctx.partitionKV.put(i, new ArrayList<>());
                jobs.put(spec.job_id, ctx);

                // Build MAP tasks by splitting input_text (line-safe)
                List<String> lines = Arrays.asList(Optional.ofNullable(spec.input_text).orElse("").split("\n"));
                int splitSize = Math.max(1, Optional.ofNullable(spec.split_size).orElse(1024));
                StringBuilder chunk = new StringBuilder();
                int currentSize = 0;
                int t = 0;
                for (String ln : lines) {
                    String l = ln + "\n";
                    if (currentSize + l.length() > splitSize && currentSize > 0) {
                        Task mt = new Task();
                        mt.type = TaskType.MAP;
                        mt.taskId = "map-" + (t++);
                        mt.jobId = spec.job_id;
                        mt.inputChunk = chunk.toString();
                        ctx.mapTasks.add(mt);
                        chunk = new StringBuilder();
                        currentSize = 0;
                    }
                    chunk.append(l);
                    currentSize += l.length();
                }
                if (chunk.length() > 0) {
                    Task mt = new Task();
                    mt.type = TaskType.MAP;
                    mt.taskId = "map-" + (t++);
                    mt.jobId = spec.job_id;
                    mt.inputChunk = chunk.toString();
                    ctx.mapTasks.add(mt);
                }

                // Enqueue initial MAP tasks
                ctx.state = JobState.RUNNING;
                for (Task mt : ctx.mapTasks) pendingTasks.offer(mt);

                respondJson(ex, 200, Map.of("job_id", spec.job_id, "maps", ctx.mapTasks.size()));
            } else if ("GET".equals(ex.getRequestMethod())) {
                // list jobs
                respondJson(ex, 200, jobs.keySet());
            } else {
                respond(ex, 405, "", "");
            }
        });

        // Job status
        server.createContext("/api/jobs/status", ex -> {
            String q = ex.getRequestURI().getQuery(); // job_id=...
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                respond(ex, 404, "not found", "text/plain");
                return;
            }
            Map<String, Object> st = new LinkedHashMap<>();
            st.put("job_id", jobId);
            st.put("state", ctx.state.toString());
            st.put("maps_total", ctx.mapTasks.size());
            st.put("maps_completed", ctx.completedMaps);
            st.put("reduces_total", ctx.spec.reducers);
            st.put("reduces_completed", ctx.completedReduces);
            respondJson(ex, 200, st);
        });

        // Job result
        server.createContext("/api/jobs/result", ex -> {
            String q = ex.getRequestURI().getQuery(); // job_id=...
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                respond(ex, 404, "not found", "text/plain");
                return;
            }
            if (ctx.state != JobState.SUCCEEDED) {
                respond(ex, 409, "not ready", "text/plain");
                return;
            }
            respond(ex, 200, ctx.finalOutput, "text/plain");
        });

        // Serve map.py / reduce.py
        server.createContext("/api/jobs/scripts", ex -> {
            String path = ex.getRequestURI().getPath(); // /api/jobs/scripts/{jobId}/{which}
            String[] parts = path.split("/");
            if (parts.length != 6) {
                respond(ex, 404, "", "");
                return;
            }
            String jobId = parts[4];
            String which = parts[5]; // map.py or reduce.py
            JobCtx ctx = jobs.get(jobId);
            if (ctx == null) {
                respond(ex, 404, "", "");
                return;
            }
            byte[] data = which.equals("map.py") ? ctx.mapScript : ctx.reduceScript;
            ex.getResponseHeaders().add("Content-Type", "text/x-python");
            ex.sendResponseHeaders(200, data.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(data);
            }
        });

        // Worker polling for next task
        server.createContext("/api/tasks/next", ex -> {
            if (!"GET".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            Task task = pendingTasks.poll();
            if (task == null) {
                respond(ex, 204, "", "");
                return;
            }
            JobCtx ctx = jobs.get(task.jobId);
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("type", task.type.toString());
            resp.put("task_id", task.taskId);
            resp.put("job_id", task.jobId);
            if (task.type == TaskType.MAP) {
                resp.put("input_chunk", task.inputChunk);
                resp.put("map_url", "/api/jobs/scripts/" + task.jobId + "/map.py");
                resp.put("reducers", ctx.spec.reducers);
            } else {
                resp.put("partition_index", task.partitionIndex);
                resp.put("reduce_url", "/api/jobs/scripts/" + task.jobId + "/reduce.py");
                // Flatten lines
                String joined = String.join("\n", task.kvLinesForReduce);
                resp.put("kv_lines", joined);
            }
            respondJson(ex, 200, resp);
        });

        // Worker completing tasks
        server.createContext("/api/tasks/complete", ex -> {
            if (!"POST".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            String body = readBody(ex);
            JsonObject j = JsonParser.parseString(body).getAsJsonObject();
            String taskId = j.get("task_id").getAsString();
            String type = j.get("type").getAsString();
            String jobId = j.get("job_id").getAsString();
            JobCtx ctx = jobs.get(jobId);
            if (ctx == null) {
                respond(ex, 404, "job not found", "text/plain");
                return;
            }

            if ("MAP".equals(type)) {
                String kv = j.get("kv_lines").getAsString(); // "k\tv\n..."
                // Shuffle: agrupar por partición
                int added = 0;
                for (String line : kv.split("\n")) {
                    if (line.isBlank()) continue;
                    String[] kvp = line.split("\t", 2);  // <--- clave: limit 2
                    if (kvp.length < 2) continue;
                    String k = kvp[0];
                    String v = kvp[1];
                    int p = partitionOf(k, ctx.spec.reducers);
                    ctx.partitionKV.get(p).add(k + "\t" + v);
                    added++;
                }
                System.out.println("[MAP COMPLETE] job=" + jobId + " task=" + taskId + " kvAdded=" + added);
                ctx.completedMaps++;

                // Cuando terminan todos los MAP: crear REDUCE tasks
                if (ctx.completedMaps == ctx.mapTasks.size()) {
                    for (int i = 0; i < ctx.spec.reducers; i++) {
                        int sz = ctx.partitionKV.get(i).size();
                        System.out.println("[SHUFFLE] job=" + jobId + " partition=" + i + " size=" + sz);
                    }
                    int rIx = 0;
                    ctx.reduceTasks.clear();
                    for (Map.Entry<Integer, List<String>> e : ctx.partitionKV.entrySet()) {
                        if (e.getValue().isEmpty()) continue; // no reducers vacíos
                        Task rt = new Task();
                        rt.type = TaskType.REDUCE;
                        rt.taskId = "reduce-" + (rIx++);
                        rt.jobId = jobId;
                        rt.partitionIndex = e.getKey();
                        rt.kvLinesForReduce = e.getValue();
                        ctx.reduceTasks.add(rt);
                        pendingTasks.offer(rt);
                    }
                    if (ctx.reduceTasks.isEmpty()) {
                        System.out.println("[REDUCE BYPASS] No data to reduce for job=" + jobId);
                        ctx.state = JobState.SUCCEEDED;
                    }
                }
                respondJson(ex, 200, Map.of("ack", true));
            } else {
                String out = j.get("output").getAsString(); // "k\tsum\n..."
                ctx.completedReduces++;
                // Concatenar en orden de partición
                ctx.finalOutput += out + (out.endsWith("\n") ? "" : "\n");
                if (ctx.completedReduces == ctx.spec.reducers) {
                    ctx.state = JobState.SUCCEEDED;
                }
                if (ctx.completedReduces == ctx.reduceTasks.size()) {
                    ctx.state = JobState.SUCCEEDED;

                    // --- S3 local: persistimos el resultado ---
                    try {
                        File dir = new File("out");
                        if (!dir.exists()) dir.mkdirs();
                        File f = new File(dir, ctx.spec.job_id + ".txt");
                        try (FileOutputStream fos = new FileOutputStream(f, false)) {
                            fos.write(ctx.finalOutput.getBytes(StandardCharsets.UTF_8));
                        }
                        System.out.println("[RESULT STORED] " + f.getAbsolutePath());
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
                respondJson(ex, 200, Map.of("ack", true));
            }
        });

        server.start();
        System.out.println("Road-Poneglyph Master listening on :8080");
    }
}
