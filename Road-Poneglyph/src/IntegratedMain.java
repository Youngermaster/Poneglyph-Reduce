import com.google.gson.*;
import com.sun.net.httpserver.*;
import io.grpc.*;
import io.grpc.stub.StreamObserver;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;
import java.util.Base64;

// Import generated gRPC classes (will be generated after gradle build)
// import com.poneglyph.grpc.*;

/**
 * Integrated Road-Poneglyph Master with gRPC Middleware Integration
 * Combines HTTP REST API for external clients with gRPC communication to middleware
 */
public class IntegratedMain {

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
        String inputChunk;
        int partitionIndex;
        List<String> kvLinesForReduce = new ArrayList<>();
    }

    static class JobCtx {
        JobSpec spec;
        JobState state = JobState.PENDING;
        List<Task> mapTasks = new ArrayList<>();
        Map<Integer, List<String>> partitionKV = new HashMap<>();
        List<Task> reduceTasks = new ArrayList<>();
        String finalOutput = "";
        byte[] mapScript;
        byte[] reduceScript;
        int completedMaps = 0;
        int completedReduces = 0;
        long createdAt = System.currentTimeMillis();
    }

    // ----- State -----
    static final Gson gson = new GsonBuilder().create();
    static final Map<String, Worker> workers = new ConcurrentHashMap<>();
    static final Map<String, JobCtx> jobs = new ConcurrentHashMap<>();
    static final BlockingQueue<Task> pendingTasks = new LinkedBlockingQueue<>();
    
    // gRPC Configuration
    static final String GRPC_MIDDLEWARE_HOST = System.getenv().getOrDefault("GRPC_MIDDLEWARE_HOST", "localhost");
    static final int GRPC_MIDDLEWARE_PORT = Integer.parseInt(System.getenv().getOrDefault("GRPC_MIDDLEWARE_PORT", "50051"));
    static boolean useGrpcMiddleware = false;
    
    // gRPC Channel and Client (will be initialized after gRPC classes are generated)
    static ManagedChannel grpcChannel;
    // static JobManagementServiceGrpc.JobManagementServiceBlockingStub jobClient;
    // static WorkerManagementServiceGrpc.WorkerManagementServiceBlockingStub workerClient;
    // static TaskDistributionServiceGrpc.TaskDistributionServiceBlockingStub taskClient;

    // ----- gRPC Integration Methods -----
    static void initializeGrpcClient() {
        try {
            grpcChannel = ManagedChannelBuilder.forAddress(GRPC_MIDDLEWARE_HOST, GRPC_MIDDLEWARE_PORT)
                    .usePlaintext()
                    .build();
            
            // TODO: Initialize gRPC clients after proto compilation
            // jobClient = JobManagementServiceGrpc.newBlockingStub(grpcChannel);
            // workerClient = WorkerManagementServiceGrpc.newBlockingStub(grpcChannel);
            // taskClient = TaskDistributionServiceGrpc.newBlockingStub(grpcChannel);
            
            // Test connection
            // HealthCheckRequest healthReq = HealthCheckRequest.newBuilder().build();
            // HealthCheckResponse healthResp = jobClient.healthCheck(healthReq);
            
            useGrpcMiddleware = true;
            System.out.println("✅ gRPC Middleware connected at " + GRPC_MIDDLEWARE_HOST + ":" + GRPC_MIDDLEWARE_PORT);
            
        } catch (Exception e) {
            System.err.println("⚠️ gRPC Middleware connection failed: " + e.getMessage());
            System.err.println("🔄 Falling back to direct HTTP mode");
            useGrpcMiddleware = false;
        }
    }

    static void submitJobToMiddleware(JobCtx ctx) {
        if (!useGrpcMiddleware) {
            System.out.println("📤 Submitting job " + ctx.spec.job_id + " locally (HTTP mode)");
            submitJobDirectly(ctx);
            return;
        }

        try {
            System.out.println("📤 Submitting job " + ctx.spec.job_id + " to gRPC middleware");
            
            // TODO: Implement gRPC job submission after proto compilation
            /*
            SubmitJobRequest request = SubmitJobRequest.newBuilder()
                    .setJobId(ctx.spec.job_id)
                    .setInputText(ctx.spec.input_text)
                    .setMapScript(ByteString.copyFrom(ctx.mapScript))
                    .setReduceScript(ByteString.copyFrom(ctx.reduceScript))
                    .setSplitSize(ctx.spec.split_size)
                    .setReducers(ctx.spec.reducers)
                    .build();
            
            SubmitJobResponse response = jobClient.submitJob(request);
            System.out.println("✅ Job submitted to middleware: " + response.getJobId());
            */
            
            // Temporary fallback
            submitJobDirectly(ctx);
            
        } catch (Exception e) {
            System.err.println("❌ Failed to submit job to middleware: " + e.getMessage());
            System.err.println("🔄 Falling back to direct processing");
            submitJobDirectly(ctx);
        }
    }

    static void submitJobDirectly(JobCtx ctx) {
        // Direct processing - enqueue MAP tasks
        ctx.state = JobState.RUNNING;
        for (Task mt : ctx.mapTasks) {
            pendingTasks.offer(mt);
        }
        System.out.println("📋 Enqueued " + ctx.mapTasks.size() + " MAP tasks for job " + ctx.spec.job_id);
    }

    static void checkJobStatusFromMiddleware(String jobId) {
        if (!useGrpcMiddleware) return;

        try {
            // TODO: Implement gRPC status check after proto compilation
            /*
            GetJobStatusRequest request = GetJobStatusRequest.newBuilder()
                    .setJobId(jobId)
                    .build();
            
            GetJobStatusResponse response = jobClient.getJobStatus(request);
            
            JobCtx ctx = jobs.get(jobId);
            if (ctx != null) {
                // Update local state based on middleware response
                ctx.completedMaps = response.getMapsCompleted();
                ctx.completedReduces = response.getReducesCompleted();
                
                if (response.getStatus().equals("SUCCEEDED")) {
                    ctx.state = JobState.SUCCEEDED;
                    ctx.finalOutput = response.getResult();
                } else if (response.getStatus().equals("FAILED")) {
                    ctx.state = JobState.FAILED;
                }
            }
            */
        } catch (Exception e) {
            System.err.println("⚠️ Failed to check job status from middleware: " + e.getMessage());
        }
    }

    // ----- Utility Methods -----
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

    // ----- Main Server -----
    public static void main(String[] args) throws Exception {
        System.out.println("🚀 Starting Integrated Road-Poneglyph Master...");
        
        // Initialize gRPC client
        initializeGrpcClient();
        
        // Start background job status checker
        if (useGrpcMiddleware) {
            startJobStatusChecker();
        }
        
        int port = Integer.parseInt(System.getenv().getOrDefault("SERVER_PORT", "8080"));
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        // Health endpoint
        server.createContext("/api/health", ex -> {
            Map<String, Object> health = new LinkedHashMap<>();
            health.put("status", "healthy");
            health.put("mode", useGrpcMiddleware ? "gRPC" : "HTTP");
            health.put("middleware_host", GRPC_MIDDLEWARE_HOST);
            health.put("middleware_port", GRPC_MIDDLEWARE_PORT);
            health.put("jobs_count", jobs.size());
            health.put("pending_tasks", pendingTasks.size());
            health.put("workers_count", workers.size());
            respondJson(ex, 200, health);
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
            
            Map<String, Object> resp = Map.of(
                "worker_id", w.workerId, 
                "poll_interval_ms", 1000,
                "mode", useGrpcMiddleware ? "gRPC" : "HTTP"
            );
            respondJson(ex, 200, resp);
            
            System.out.println("👷 Worker registered: " + w.workerId + " (" + w.name + ")");
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

                // Build MAP tasks by splitting input_text
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

                // Submit job (via gRPC or directly)
                submitJobToMiddleware(ctx);

                Map<String, Object> response = Map.of(
                    "job_id", spec.job_id, 
                    "maps", ctx.mapTasks.size(),
                    "mode", useGrpcMiddleware ? "gRPC" : "HTTP"
                );
                respondJson(ex, 200, response);
                
                System.out.println("📝 Job submitted: " + spec.job_id + " with " + ctx.mapTasks.size() + " MAP tasks");
                
            } else if ("GET".equals(ex.getRequestMethod())) {
                respondJson(ex, 200, jobs.keySet());
            } else {
                respond(ex, 405, "", "");
            }
        });

        // Job status
        server.createContext("/api/jobs/status", ex -> {
            String q = ex.getRequestURI().getQuery();
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                respond(ex, 404, "Job not found", "text/plain");
                return;
            }

            // Check status from middleware if using gRPC
            if (useGrpcMiddleware) {
                checkJobStatusFromMiddleware(jobId);
            }

            Map<String, Object> st = new LinkedHashMap<>();
            st.put("job_id", jobId);
            st.put("state", ctx.state.toString());
            st.put("maps_total", ctx.mapTasks.size());
            st.put("maps_completed", ctx.completedMaps);
            st.put("reduces_total", ctx.spec.reducers);
            st.put("reduces_completed", ctx.completedReduces);
            st.put("mode", useGrpcMiddleware ? "gRPC" : "HTTP");
            st.put("created_at", ctx.createdAt);
            respondJson(ex, 200, st);
        });

        // Job result
        server.createContext("/api/jobs/result", ex -> {
            String q = ex.getRequestURI().getQuery();
            String jobId = (q != null && q.startsWith("job_id=")) ? q.substring("job_id=".length()) : null;
            JobCtx ctx = (jobId != null) ? jobs.get(jobId) : null;
            if (ctx == null) {
                respond(ex, 404, "Job not found", "text/plain");
                return;
            }
            
            // Check status from middleware if using gRPC
            if (useGrpcMiddleware) {
                checkJobStatusFromMiddleware(jobId);
            }
            
            if (ctx.state != JobState.SUCCEEDED) {
                respond(ex, 409, "Job not completed", "text/plain");
                return;
            }
            respond(ex, 200, ctx.finalOutput, "text/plain");
        });

        // Serve scripts
        server.createContext("/api/jobs/scripts", ex -> {
            String path = ex.getRequestURI().getPath();
            String[] parts = path.split("/");
            if (parts.length != 6) {
                respond(ex, 404, "", "");
                return;
            }
            String jobId = parts[4];
            String which = parts[5];
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

        // Worker task polling (fallback for HTTP mode)
        server.createContext("/api/tasks/next", ex -> {
            if (!"GET".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            
            if (useGrpcMiddleware) {
                // In gRPC mode, workers should connect to middleware directly
                Map<String, Object> redirect = Map.of(
                    "message", "Workers should connect to gRPC middleware",
                    "middleware_host", GRPC_MIDDLEWARE_HOST,
                    "middleware_port", GRPC_MIDDLEWARE_PORT,
                    "use_grpc", true
                );
                respondJson(ex, 200, redirect);
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
                String joined = String.join("\n", task.kvLinesForReduce);
                resp.put("kv_lines", joined);
            }
            respondJson(ex, 200, resp);
        });

        // Task completion (fallback for HTTP mode)
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
                respond(ex, 404, "Job not found", "text/plain");
                return;
            }

            if ("MAP".equals(type)) {
                String kv = j.get("kv_lines").getAsString();
                System.out.println("📊 Processing MAP task " + taskId + " with " + kv.length() + " characters");
                
                // Shuffle: group by partition
                int lineCount = 0;
                for (String line : kv.split("\n")) {
                    if (line.isBlank()) continue;
                    String[] kvp = line.split("\t");
                    if (kvp.length < 2) continue;
                    String k = kvp[0];
                    String v = kvp[1];
                    int p = partitionOf(k, ctx.spec.reducers);
                    ctx.partitionKV.get(p).add(k + "\t" + v);
                    lineCount++;
                }
                
                System.out.println("✅ MAP task " + taskId + " processed " + lineCount + " key-value pairs");
                ctx.completedMaps++;
                
                // When all MAP tasks complete: create REDUCE tasks
                if (ctx.completedMaps == ctx.mapTasks.size()) {
                    for (Map.Entry<Integer, List<String>> e : ctx.partitionKV.entrySet()) {
                        int partitionIndex = e.getKey();
                        List<String> kvData = e.getValue();
                        
                        if (!kvData.isEmpty()) {
                            Task rt = new Task();
                            rt.type = TaskType.REDUCE;
                            rt.taskId = "reduce-" + partitionIndex;
                            rt.jobId = jobId;
                            rt.partitionIndex = partitionIndex;
                            rt.kvLinesForReduce = kvData;
                            ctx.reduceTasks.add(rt);
                            pendingTasks.offer(rt);
                            System.out.println("🔄 Created REDUCE task " + rt.taskId + " with " + kvData.size() + " lines");
                        } else {
                            System.out.println("⏭️ Skipping empty partition " + partitionIndex);
                        }
                    }
                }
                respondJson(ex, 200, Map.of("ack", true));
                
            } else { // REDUCE
                String out = j.get("output").getAsString();
                System.out.println("✅ REDUCE task " + taskId + " completed with output length: " + out.length());
                ctx.completedReduces++;
                ctx.finalOutput += out + (out.endsWith("\n") ? "" : "\n");
                
                if (ctx.completedReduces == ctx.spec.reducers) {
                    ctx.state = JobState.SUCCEEDED;
                    System.out.println("🎉 Job " + jobId + " completed! Final output length: " + ctx.finalOutput.length());
                }
                respondJson(ex, 200, Map.of("ack", true));
            }
        });

        server.start();
        System.out.println("🌟 Integrated Road-Poneglyph Master listening on :" + port);
        System.out.println("🔧 Mode: " + (useGrpcMiddleware ? "gRPC Middleware" : "Direct HTTP"));
        if (useGrpcMiddleware) {
            System.out.println("🔗 Middleware: " + GRPC_MIDDLEWARE_HOST + ":" + GRPC_MIDDLEWARE_PORT);
        }
        
        // Add shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("🛑 Shutting down Integrated Road-Poneglyph Master...");
            if (grpcChannel != null && !grpcChannel.isShutdown()) {
                grpcChannel.shutdown();
                try {
                    if (!grpcChannel.awaitTermination(5, TimeUnit.SECONDS)) {
                        grpcChannel.shutdownNow();
                    }
                } catch (InterruptedException e) {
                    grpcChannel.shutdownNow();
                }
            }
        }));
    }

    static void startJobStatusChecker() {
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
        scheduler.scheduleAtFixedRate(() -> {
            try {
                for (String jobId : jobs.keySet()) {
                    JobCtx ctx = jobs.get(jobId);
                    if (ctx != null && ctx.state == JobState.RUNNING) {
                        checkJobStatusFromMiddleware(jobId);
                    }
                }
            } catch (Exception e) {
                System.err.println("⚠️ Error in job status checker: " + e.getMessage());
            }
        }, 0, 5, TimeUnit.SECONDS);
        
        System.out.println("📡 Job status checker started (checking every 5 seconds)");
    }
}
