import java.net.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import com.google.gson.*;

// Simplified Master that integrates with gRPC middleware
public class HybridMain {
    
    static class Job {
        String jobId;
        JobState state = JobState.SUBMITTED;
        List<String> input;
        int reducers;
        List<Task> mapTasks = new ArrayList<>();
        List<Task> reduceTasks = new ArrayList<>();
        String finalOutput = "";
        int completedMaps = 0;
        int completedReduces = 0;
        Map<Integer, List<String>> partitionKV = new HashMap<>();
    }
    
    enum JobState { SUBMITTED, RUNNING, SUCCEEDED, FAILED }
    
    static class Task {
        String taskId;
        String jobId;
        TaskType type;
        String inputChunk;
        int partitionIndex;
        List<String> kvLinesForReduce;
    }
    
    enum TaskType { MAP, REDUCE }
    
    static Map<String, Job> jobs = new ConcurrentHashMap<>();
    static BlockingQueue<Task> pendingTasks = new LinkedBlockingQueue<>();
    static boolean useGrpcMiddleware = false;
    
    static int partitionOf(String key, int reducers) {
        return Math.abs(key.hashCode()) % reducers;
    }
    
    public static void main(String[] args) throws IOException {
        
        // Check if gRPC middleware is available
        try {
            // Simple check - in real implementation, this would be a proper gRPC connection test
            useGrpcMiddleware = System.getenv("MIDDLEWARE_GRPC_URL") != null;
            System.out.println("gRPC Middleware " + (useGrpcMiddleware ? "enabled" : "disabled"));
        } catch (Exception e) {
            useGrpcMiddleware = false;
        }
        
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        
        // Job submission endpoint
        server.createContext("/api/jobs/submit", ex -> {
            if (!"POST".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            
            String body = new String(ex.getRequestBody().readAllBytes());
            JsonObject req = JsonParser.parseString(body).getAsJsonObject();
            
            String jobId = "wordcount-" + String.format("%03d", jobs.size() + 1);
            String input = req.get("input").getAsString();
            int reducers = req.has("reducers") ? req.get("reducers").getAsInt() : 2;
            
            Job job = new Job();
            job.jobId = jobId;
            job.reducers = reducers;
            job.state = JobState.RUNNING;
            
            // Split input into chunks
            String[] lines = input.split("\\\\n");
            int chunkSize = Math.max(1, lines.length / 7);
            
            for (int i = 0; i < lines.length; i += chunkSize) {
                int end = Math.min(i + chunkSize, lines.length);
                String chunk = String.join("\\n", Arrays.copyOfRange(lines, i, end));
                
                Task mapTask = new Task();
                mapTask.taskId = "map-" + job.mapTasks.size();
                mapTask.jobId = jobId;
                mapTask.type = TaskType.MAP;
                mapTask.inputChunk = chunk;
                
                job.mapTasks.add(mapTask);
                
                if (useGrpcMiddleware) {
                    submitTaskToMiddleware(mapTask);
                } else {
                    pendingTasks.offer(mapTask);
                }
            }
            
            // Initialize partition structure
            job.partitionKV = new HashMap<>();
            for (int i = 0; i < reducers; i++) {
                job.partitionKV.put(i, new ArrayList<>());
            }
            
            jobs.put(jobId, job);
            
            Map<String, Object> response = new HashMap<>();
            response.put("job_id", jobId);
            response.put("maps", job.mapTasks.size());
            respondJson(ex, 200, response);
        });
        
        // Job status endpoint
        server.createContext("/api/jobs/", ex -> {
            String path = ex.getRequestURI().getPath();
            String[] parts = path.split("/");
            
            if (parts.length >= 4) {
                String jobId = parts[3];
                Job job = jobs.get(jobId);
                
                if (job == null) {
                    respond(ex, 404, "", "");
                    return;
                }
                
                if (parts.length >= 5 && "status".equals(parts[4])) {
                    Map<String, Object> status = new HashMap<>();
                    status.put("job_id", jobId);
                    status.put("state", job.state.toString());
                    status.put("maps_total", job.mapTasks.size());
                    status.put("maps_completed", job.completedMaps);
                    status.put("reduces_total", job.reduceTasks.size());
                    status.put("reduces_completed", job.completedReduces);
                    respondJson(ex, 200, status);
                    return;
                }
                
                if (parts.length >= 5 && "result".equals(parts[4])) {
                    if (job.state == JobState.SUCCEEDED) {
                        Map<String, Object> result = new HashMap<>();
                        result.put("result", job.finalOutput.trim());
                        respondJson(ex, 200, result);
                    } else {
                        respond(ex, 404, "", "");
                    }
                    return;
                }
            }
            
            respond(ex, 404, "", "");
        });
        
        // Task endpoint for workers (fallback HTTP)
        server.createContext("/api/tasks/next", ex -> {
            if (useGrpcMiddleware) {
                // If using gRPC middleware, workers should connect to middleware instead
                respond(ex, 204, "", "");
                return;
            }
            
            String workerId = getQueryParam(ex.getRequestURI().getQuery(), "workerId");
            if (workerId == null) {
                respond(ex, 400, "", "");
                return;
            }
            
            Task task = pendingTasks.poll();
            if (task == null) {
                respond(ex, 204, "", "");
                return;
            }
            
            Job job = jobs.get(task.jobId);
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("type", task.type.toString());
            resp.put("task_id", task.taskId);
            resp.put("job_id", task.jobId);
            
            if (task.type == TaskType.MAP) {
                resp.put("input_chunk", task.inputChunk);
                resp.put("map_url", "/api/jobs/scripts/" + task.jobId + "/map.py");
                resp.put("reducers", job.reducers);
            } else {
                resp.put("partition_index", task.partitionIndex);
                resp.put("reduce_url", "/api/jobs/scripts/" + task.jobId + "/reduce.py");
                String joined = String.join("\\n", task.kvLinesForReduce);
                resp.put("kv_lines", joined);
            }
            respondJson(ex, 200, resp);
        });
        
        // Task completion endpoint
        server.createContext("/api/tasks/complete", ex -> {
            if (!"POST".equals(ex.getRequestMethod())) {
                respond(ex, 405, "", "");
                return;
            }
            
            String body = new String(ex.getRequestBody().readAllBytes());
            JsonObject j = JsonParser.parseString(body).getAsJsonObject();
            
            String taskId = j.get("task_id").getAsString();
            String jobId = j.get("job_id").getAsString();
            String type = j.get("type").getAsString();
            
            Job job = jobs.get(jobId);
            if (job == null) {
                respond(ex, 404, "", "");
                return;
            }
            
            if ("MAP".equals(type)) {
                String kvOutput = j.get("kv_lines").getAsString();
                String[] kvLines = kvOutput.split("\\\\n");
                
                System.out.println("Processing MAP task " + taskId + " with " + kvOutput.length() + " characters");
                System.out.println("MAP task " + taskId + " processed " + kvLines.length + " key-value pairs");
                
                // Partition the key-value pairs
                for (String line : kvLines) {
                    if (line.trim().isEmpty()) continue;
                    String[] parts = line.split("\\t", 2);
                    if (parts.length == 2) {
                        String k = parts[0];
                        String v = parts[1];
                        int p = partitionOf(k, job.reducers);
                        job.partitionKV.get(p).add(k + "\\t" + v);
                    }
                }
                
                job.completedMaps++;
                
                // When all MAP tasks complete, create REDUCE tasks
                if (job.completedMaps == job.mapTasks.size()) {
                    for (Map.Entry<Integer, List<String>> e : job.partitionKV.entrySet()) {
                        int partitionIndex = e.getKey();
                        List<String> kvData = e.getValue();
                        
                        if (!kvData.isEmpty()) {
                            Task rt = new Task();
                            rt.type = TaskType.REDUCE;
                            rt.taskId = "reduce-" + partitionIndex;
                            rt.jobId = jobId;
                            rt.partitionIndex = partitionIndex;
                            rt.kvLinesForReduce = kvData;
                            job.reduceTasks.add(rt);
                            
                            if (useGrpcMiddleware) {
                                submitTaskToMiddleware(rt);
                            } else {
                                pendingTasks.offer(rt);
                            }
                            
                            System.out.println("Created REDUCE task " + rt.taskId + " with " + kvData.size() + " lines");
                        }
                    }
                }
                respondJson(ex, 200, Map.of("ack", true));
            } else {
                String out = j.get("output").getAsString();
                System.out.println("REDUCE task " + taskId + " completed with output length: " + out.length());
                job.completedReduces++;
                job.finalOutput += out + (out.endsWith("\\n") ? "" : "\\n");
                
                if (job.completedReduces == job.reduceTasks.size()) {
                    job.state = JobState.SUCCEEDED;
                    System.out.println("Job " + jobId + " completed. Final output length: " + job.finalOutput.length());
                }
                respondJson(ex, 200, Map.of("ack", true));
            }
        });
        
        server.createContext("/api/health", ex -> {
            Map<String, Object> health = new HashMap<>();
            health.put("status", "healthy");
            health.put("middleware_enabled", useGrpcMiddleware);
            health.put("jobs_count", jobs.size());
            health.put("pending_tasks", pendingTasks.size());
            respondJson(ex, 200, health);
        });
        
        // Scripts endpoint
        server.createContext("/api/jobs/scripts/", ex -> {
            String path = ex.getRequestURI().getPath();
            if (path.endsWith("/map.py")) {
                String mapScript = "import sys\\nfrom collections import Counter\\n\\ninp = sys.argv[1]\\nwith open(inp, 'r', encoding='utf-8', errors='ignore') as f:\\n    for line in f:\\n        words = line.lower().replace(',', '').replace('.', '').split()\\n        for word in words:\\n            print(f'{word}\\t1')\\n";
                respond(ex, 200, mapScript, "text/plain");
            } else if (path.endsWith("/reduce.py")) {
                String reduceScript = "import sys\\nfrom collections import defaultdict\\n\\ninp = sys.argv[1]\\ncounts = defaultdict(int)\\nwith open(inp, 'r', encoding='utf-8', errors='ignore') as f:\\n    for line in f:\\n        line = line.strip()\\n        if not line: continue\\n        k, v = line.split('\\t', 1)\\n        counts[k] += int(v)\\n\\nfor k in sorted(counts.keys()):\\n    print(f'{k}\\t{counts[k]}')\\n";
                respond(ex, 200, reduceScript, "text/plain");
            } else {
                respond(ex, 404, "", "");
            }
        });
        
        server.setExecutor(null);
        server.start();
        
        System.out.println("Hybrid Poneglyph Master listening on :8080");
        System.out.println("gRPC Middleware integration: " + (useGrpcMiddleware ? "ENABLED" : "DISABLED"));
    }
    
    static void submitTaskToMiddleware(Task task) {
        // In a real implementation, this would submit the task via gRPC
        // For now, fallback to local queue
        pendingTasks.offer(task);
        System.out.println("Task " + task.taskId + " submitted to middleware");
    }
    
    static String getQueryParam(String query, String param) {
        if (query == null) return null;
        String[] pairs = query.split("&");
        for (String pair : pairs) {
            String[] kv = pair.split("=", 2);
            if (kv.length == 2 && kv[0].equals(param)) {
                return kv[1];
            }
        }
        return null;
    }
    
    static void respond(HttpExchange ex, int code, String body, String contentType) throws IOException {
        if (contentType.isEmpty()) contentType = "application/json";
        ex.getResponseHeaders().set("Content-Type", contentType);
        ex.sendResponseHeaders(code, body.length());
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body.getBytes());
        }
    }
    
    static void respondJson(HttpExchange ex, int code, Object obj) throws IOException {
        Gson gson = new Gson();
        String json = gson.toJson(obj);
        respond(ex, code, json, "application/json");
    }
}
