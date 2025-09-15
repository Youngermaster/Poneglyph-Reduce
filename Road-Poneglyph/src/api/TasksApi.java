package api;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import core.Partitioner;
import core.Scheduler;
import core.SmartScheduler;
import http.HttpUtils;
import model.*;
import store.RedisStore;
import telemetry.MqttClientManager;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.BlockingQueue;

public final class TasksApi {
    private TasksApi() {
    }

    /**
     * GET /api/tasks/next
     */
    public static class NextHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;
        private final BlockingQueue<Task> pending;

        public NextHandler(Map<String, JobCtx> jobs, BlockingQueue<Task> pending) {
            this.jobs = jobs;
            this.pending = pending;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            if (!"GET".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }

            Task task = pending.poll();
            if (task == null) {
                HttpUtils.respond(ex, 204, "", "");
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
                resp.put("kv_lines", String.join("\n", task.kvLinesForReduce));
            }
            HttpUtils.respondJson(ex, 200, resp);
        }
    }

    /**
     * POST /api/tasks/complete
     */
    public static class CompleteHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;
        private final Scheduler scheduler;
        private final MqttClientManager mqtt;
        private final RedisStore redis;

        public CompleteHandler(Map<String, JobCtx> jobs, Scheduler scheduler, MqttClientManager mqtt, RedisStore redis) {
            this.jobs = jobs;
            this.scheduler = scheduler;
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

            String taskId = j.get("task_id").getAsString();
            String type = j.get("type").getAsString();
            String jobId = j.get("job_id").getAsString();

            JobCtx ctx = jobs.get(jobId);
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "job not found", "text/plain");
                return;
            }

            if ("MAP".equals(type)) {
                String kv = j.get("kv_lines").getAsString(); // "k\tv\n..."
                int added = 0;
                for (String line : kv.split("\n")) {
                    if (line.isBlank()) continue;
                    String[] kvp = line.split("\t", 2);
                    if (kvp.length < 2) continue;
                    String k = kvp[0];
                    String v = kvp[1];
                    int p = core.Partitioner.partitionOf(k, ctx.spec.reducers);
                    ctx.partitionKV.get(p).add(k + "\t" + v);
                    added++;
                }
                ctx.completedMaps++;
                System.out.println("[MAP COMPLETE] job=" + jobId + " task=" + taskId + " kvAdded=" + added);

                if (mqtt != null) {
                    mqtt.publishJson("gridmr/job/" + jobId + "/map/completed", Map.of(
                            "taskId", taskId, "added", added, "mapsCompleted", ctx.completedMaps, "ts", System.currentTimeMillis()
                    ));
                }
                if (redis != null) {
                    redis.saveJobCounters(jobId, ctx.completedMaps, ctx.completedReduces);
                }

                if (ctx.completedMaps == ctx.mapTasks.size()) {
                    // build reduce tasks only for non-empty partitions
                    int rIx = 0;
                    ctx.reduceTasks.clear();
                    var sizes = new java.util.ArrayList<Integer>();

                    for (int i = 0; i < ctx.spec.reducers; i++) {
                        int sz = ctx.partitionKV.get(i).size();
                        sizes.add(sz);
                        if (sz == 0) continue;

                        Task rt = new Task();
                        rt.type = TaskType.REDUCE;
                        rt.taskId = "reduce-" + (rIx++);
                        rt.jobId = jobId;
                        rt.partitionIndex = i;
                        rt.kvLinesForReduce = ctx.partitionKV.get(i);
                        ctx.reduceTasks.add(rt);
                        scheduler.enqueue(rt);
                    }
                    if (mqtt != null) {
                        mqtt.publishJson("gridmr/job/" + jobId + "/shuffle/partitions", Map.of(
                                "sizes", sizes, "ts", System.currentTimeMillis()
                        ));
                    }
                    if (redis != null) {
                        redis.savePartitionSizes(jobId, sizes);
                    }
                    if (ctx.reduceTasks.isEmpty()) {
                        ctx.state = JobState.SUCCEEDED;
                        Scheduler.persistResult(ctx);
                        if (redis != null) {
                            redis.setJobState(jobId, ctx.state.toString());
                            redis.storeFinalResult(jobId, ctx.finalOutput);
                        }
                        if (mqtt != null) {
                            mqtt.publishJson("gridmr/job/" + jobId + "/state", Map.of(
                                    "state", ctx.state.toString(), "ts", System.currentTimeMillis()
                            ));
                        }
                    }
                }
                HttpUtils.respondJson(ex, 200, Map.of("ack", true));
                return;
            }

            // REDUCE
            String out = j.get("output").getAsString(); // "k\tsum\n..."
            ctx.completedReduces++;
            ctx.finalOutput += out + (out.endsWith("\n") ? "" : "\n");

            if (mqtt != null) {
                mqtt.publishJson("gridmr/job/" + jobId + "/reduce/completed", Map.of(
                        "taskId", taskId, "reducesCompleted", ctx.completedReduces, "ts", System.currentTimeMillis()
                ));
            }
            if (redis != null) {
                redis.saveJobCounters(jobId, ctx.completedMaps, ctx.completedReduces);
            }

            if (ctx.completedReduces == ctx.reduceTasks.size()) {
                ctx.state = JobState.SUCCEEDED;
                Scheduler.persistResult(ctx);
                if (redis != null) {
                    redis.setJobState(jobId, ctx.state.toString());
                    redis.storeFinalResult(jobId, ctx.finalOutput);
                }
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/job/" + jobId + "/state", Map.of(
                            "state", ctx.state.toString(), "ts", System.currentTimeMillis()
                    ));
                }
            }
            HttpUtils.respondJson(ex, 200, Map.of("ack", true));
        }
    }

    /**
     * GET /api/tasks/next - Versión inteligente que usa SmartScheduler
     */
    public static class SmartNextHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;
        private final SmartScheduler smartScheduler;

        public SmartNextHandler(Map<String, JobCtx> jobs, SmartScheduler smartScheduler) {
            this.jobs = jobs;
            this.smartScheduler = smartScheduler;
        }

        @Override
        public void handle(HttpExchange ex) throws IOException {
            if (!"GET".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }

            // Obtener workerId del query parameter
            String query = ex.getRequestURI().getQuery();
            String workerId = null;
            if (query != null) {
                for (String param : query.split("&")) {
                    String[] keyValue = param.split("=", 2);
                    if (keyValue.length == 2 && "workerId".equals(keyValue[0])) {
                        workerId = keyValue[1];
                        break;
                    }
                }
            }

            if (workerId == null) {
                HttpUtils.respond(ex, 400, "workerId parameter required", "text/plain");
                return;
            }

            // Usar el scheduler inteligente para obtener la mejor tarea para este worker
            Task task = smartScheduler.getNextTaskForWorker(workerId);
            if (task == null) {
                HttpUtils.respond(ex, 204, "", "");
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
                resp.put("kv_lines", String.join("\n", task.kvLinesForReduce));
            }
            HttpUtils.respondJson(ex, 200, resp);
        }
    }

    /**
     * POST /api/tasks/complete - Versión inteligente que usa SmartScheduler
     */
    public static class SmartCompleteHandler implements HttpHandler {
        private final Map<String, JobCtx> jobs;
        private final SmartScheduler smartScheduler;
        private final MqttClientManager mqtt;
        private final RedisStore redis;

        public SmartCompleteHandler(Map<String, JobCtx> jobs, SmartScheduler smartScheduler, MqttClientManager mqtt, RedisStore redis) {
            this.jobs = jobs;
            this.smartScheduler = smartScheduler;
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

            String taskId = j.get("task_id").getAsString();
            String type = j.get("type").getAsString();
            String jobId = j.get("job_id").getAsString();
            String workerId = j.has("worker_id") ? j.get("worker_id").getAsString() : null;

            JobCtx ctx = jobs.get(jobId);
            if (ctx == null) {
                HttpUtils.respond(ex, 404, "job not found", "text/plain");
                return;
            }

            // Notificar al scheduler que la tarea se completó
            if (workerId != null) {
                smartScheduler.onTaskCompleted(taskId, workerId);
            }

            if ("MAP".equals(type)) {
                String kv = j.get("kv_lines").getAsString(); // "k\tv\n..."
                int added = 0;
                for (String line : kv.split("\n")) {
                    if (line.isBlank()) continue;
                    String[] kvp = line.split("\t", 2);
                    if (kvp.length < 2) continue;
                    String k = kvp[0];
                    String v = kvp[1];
                    int p = core.Partitioner.partitionOf(k, ctx.spec.reducers);
                    ctx.partitionKV.get(p).add(k + "\t" + v);
                    added++;
                }
                ctx.completedMaps++;
                System.out.println("[MAP COMPLETE] job=" + jobId + " task=" + taskId + " kvAdded=" + added);

                if (mqtt != null) {
                    mqtt.publishJson("gridmr/job/" + jobId + "/map/completed", Map.of(
                            "taskId", taskId, "added", added, "mapsCompleted", ctx.completedMaps, "ts", System.currentTimeMillis()
                    ));
                }
                if (redis != null) {
                    redis.saveJobCounters(jobId, ctx.completedMaps, ctx.completedReduces);
                }

                if (ctx.completedMaps == ctx.mapTasks.size()) {
                    // build reduce tasks only for non-empty partitions
                    int rIx = 0;
                    ctx.reduceTasks.clear();
                    var sizes = new java.util.ArrayList<Integer>();

                    for (int i = 0; i < ctx.spec.reducers; i++) {
                        int sz = ctx.partitionKV.get(i).size();
                        sizes.add(sz);
                        if (sz == 0) continue;

                        Task rt = new Task();
                        rt.type = TaskType.REDUCE;
                        rt.taskId = "reduce-" + (rIx++);
                        rt.jobId = jobId;
                        rt.partitionIndex = i;
                        rt.kvLinesForReduce = ctx.partitionKV.get(i);
                        ctx.reduceTasks.add(rt);
                        smartScheduler.enqueue(rt); // Usar smartScheduler
                    }
                    if (mqtt != null) {
                        mqtt.publishJson("gridmr/job/" + jobId + "/shuffle/partitions", Map.of(
                                "sizes", sizes, "ts", System.currentTimeMillis()
                        ));
                    }
                    if (redis != null) {
                        redis.savePartitionSizes(jobId, sizes);
                    }
                    if (ctx.reduceTasks.isEmpty()) {
                        ctx.state = JobState.SUCCEEDED;
                        Scheduler.persistResult(ctx);
                        if (redis != null) {
                            redis.setJobState(jobId, ctx.state.toString());
                            redis.storeFinalResult(jobId, ctx.finalOutput);
                        }
                        if (mqtt != null) {
                            mqtt.publishJson("gridmr/job/" + jobId + "/state", Map.of(
                                    "state", ctx.state.toString(), "ts", System.currentTimeMillis()
                            ));
                        }
                    }
                }
                HttpUtils.respondJson(ex, 200, Map.of("ack", true));
                return;
            }

            // REDUCE
            String out = j.get("output").getAsString(); // "k\tsum\n..."
            ctx.completedReduces++;
            ctx.finalOutput += out + (out.endsWith("\n") ? "" : "\n");

            if (mqtt != null) {
                mqtt.publishJson("gridmr/job/" + jobId + "/reduce/completed", Map.of(
                        "taskId", taskId, "reducesCompleted", ctx.completedReduces, "ts", System.currentTimeMillis()
                ));
            }
            if (redis != null) {
                redis.saveJobCounters(jobId, ctx.completedMaps, ctx.completedReduces);
            }

            if (ctx.completedReduces == ctx.reduceTasks.size()) {
                ctx.state = JobState.SUCCEEDED;
                Scheduler.persistResult(ctx);
                if (redis != null) {
                    redis.setJobState(jobId, ctx.state.toString());
                    redis.storeFinalResult(jobId, ctx.finalOutput);
                }
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/job/" + jobId + "/state", Map.of(
                            "state", ctx.state.toString(), "ts", System.currentTimeMillis()
                    ));
                }
            }
            HttpUtils.respondJson(ex, 200, Map.of("ack", true));
        }
    }
}
