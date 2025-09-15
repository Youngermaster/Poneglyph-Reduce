package rpc;

import com.google.gson.Gson;
import gridmr.*;
import core.Scheduler;
import http.HttpUtils;
import model.*;
import store.RedisStore;
import telemetry.MqttClientManager;
import io.grpc.stub.StreamObserver;

import java.util.*;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentMap;

public class MasterService extends MasterGrpc.MasterImplBase {
    private static final Gson GSON = new Gson();

    private final ConcurrentMap<String, Worker> workers;
    private final ConcurrentMap<String, JobCtx> jobs;
    private final BlockingQueue<Task> pending;
    private final Scheduler scheduler;
    private final MqttClientManager mqtt;
    private final RedisStore redis;

    public MasterService(ConcurrentMap<String, Worker> workers,
                         ConcurrentMap<String, JobCtx> jobs,
                         BlockingQueue<Task> pending,
                         Scheduler scheduler,
                         MqttClientManager mqtt,
                         RedisStore redis) {
        this.workers = workers;
        this.jobs = jobs;
        this.pending = pending;
        this.scheduler = scheduler;
        this.mqtt = mqtt;
        this.redis = redis;
    }

    // ---- Register ----
    @Override
    public void register(WorkerRegisterRequest req, StreamObserver<WorkerRegisterResponse> respObs) {
        Worker w = new Worker();
        w.workerId = "w-" + java.util.UUID.randomUUID();
        w.name = (req.getName() == null || req.getName().isBlank()) ? w.workerId : req.getName();
        w.capacity = req.getCapacity() <= 0 ? 1 : req.getCapacity();
        workers.put(w.workerId, w);

        if (redis != null) redis.saveWorker(w);
        if (mqtt != null) mqtt.publishJson("gridmr/worker/registered", Map.of(
                "workerId", w.workerId, "name", w.name, "capacity", w.capacity, "ts", System.currentTimeMillis()
        ));

        respObs.onNext(WorkerRegisterResponse.newBuilder()
                .setWorkerId(w.workerId)
                .setPollIntervalMs(1000)
                .build());
        respObs.onCompleted();
    }

    // ---- NextTask ----
    @Override
    public void nextTask(NextTaskRequest req, StreamObserver<TaskAssignment> respObs) {
        Task task = pending.poll();
        if (task == null) {
            respObs.onNext(TaskAssignment.newBuilder().setHasTask(false).build());
            respObs.onCompleted();
            return;
        }
        JobCtx ctx = jobs.get(task.jobId);

        TaskAssignment.Builder out = TaskAssignment.newBuilder().setHasTask(true);
        if (task.type == TaskType.MAP) {
            MapTask.Builder mt = MapTask.newBuilder()
                    .setTaskId(task.taskId)
                    .setJobId(task.jobId)
                    .setInputChunk(task.inputChunk == null ? "" : task.inputChunk)
                    .setMapUrl("/api/jobs/scripts/" + task.jobId + "/map.py")
                    .setReducers(ctx.spec.reducers == null ? 1 : ctx.spec.reducers);
            // opcional: enviar script embebido
            if (ctx.mapScript != null && ctx.mapScript.length > 0)
                mt.setMapScript(com.google.protobuf.ByteString.copyFrom(ctx.mapScript));
            out.setMap(mt);
        } else {
            ReduceTask.Builder rt = ReduceTask.newBuilder()
                    .setTaskId(task.taskId)
                    .setJobId(task.jobId)
                    .setPartitionIndex(task.partitionIndex)
                    .setReduceUrl("/api/jobs/scripts/" + task.jobId + "/reduce.py")
                    .setKvLines(String.join("\n", task.kvLinesForReduce));
            if (ctx.reduceScript != null && ctx.reduceScript.length > 0)
                rt.setReduceScript(com.google.protobuf.ByteString.copyFrom(ctx.reduceScript));
            out.setReduce(rt);
        }
        respObs.onNext(out.build());
        respObs.onCompleted();
    }

    // ---- CompleteMap ----
    @Override
    public void completeMap(CompleteMapRequest req, StreamObserver<Ack> respObs) {
        String jobId = req.getJobId();
        JobCtx ctx = jobs.get(jobId);
        if (ctx == null) {
            respObs.onNext(Ack.newBuilder().setOk(false).build());
            respObs.onCompleted();
            return;
        }

        String kv = req.getKvLines();
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
        System.out.println("[MAP COMPLETE gRPC] job=" + jobId + " task=" + req.getTaskId() + " kvAdded=" + added);

        if (mqtt != null) {
            mqtt.publishJson("gridmr/job/" + jobId + "/map/completed", Map.of(
                    "taskId", req.getTaskId(), "added", added, "mapsCompleted", ctx.completedMaps, "ts", System.currentTimeMillis()
            ));
        }
        if (redis != null) {
            redis.saveJobCounters(jobId, ctx.completedMaps, ctx.completedReduces);
        }

        if (ctx.completedMaps == ctx.mapTasks.size()) {
            int rIx = 0;
            ctx.reduceTasks.clear();
            var sizes = new ArrayList<Integer>();

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
            if (redis != null) redis.savePartitionSizes(jobId, sizes);

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

        respObs.onNext(Ack.newBuilder().setOk(true).build());
        respObs.onCompleted();
    }

    // ---- CompleteReduce ----
    @Override
    public void completeReduce(CompleteReduceRequest req, StreamObserver<Ack> respObs) {
        String jobId = req.getJobId();
        JobCtx ctx = jobs.get(jobId);
        if (ctx == null) {
            respObs.onNext(Ack.newBuilder().setOk(false).build());
            respObs.onCompleted();
            return;
        }

        String out = req.getOutput();
        ctx.completedReduces++;
        ctx.finalOutput += out + (out.endsWith("\n") ? "" : "\n");

        if (mqtt != null) {
            mqtt.publishJson("gridmr/job/" + jobId + "/reduce/completed", Map.of(
                    "taskId", req.getTaskId(), "reducesCompleted", ctx.completedReduces, "ts", System.currentTimeMillis()
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

        respObs.onNext(Ack.newBuilder().setOk(true).build());
        respObs.onCompleted();
    }
}
