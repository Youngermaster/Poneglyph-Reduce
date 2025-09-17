import com.sun.net.httpserver.HttpServer;

import api.JobsApi;
import api.TasksApi;
import api.WorkersApi;
import core.Scheduler;
import core.SmartScheduler;
import grpc.gRPCUtils;
import http.HttpUtils;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import model.JobCtx;
import model.Task;
import model.Worker;
import rpc.MasterService;
import store.RedisStore;
import telemetry.MqttClientManager;

import java.net.InetSocketAddress;
import java.util.Map;
import java.util.concurrent.*;

public class Main {

    private static final Map<String, Worker> workers = new ConcurrentHashMap<>();
    private static final Map<String, JobCtx> jobs = new ConcurrentHashMap<>();
    private static final BlockingQueue<Task> pendingTasks = new LinkedBlockingQueue<>();
    private static SmartScheduler smartScheduler;
    private static final Scheduler scheduler = new Scheduler(pendingTasks);

    public static void main(String[] args) throws Exception {
        // Infra managers (optional if services are down)
        MqttClientManager mqtt = MqttClientManager.fromEnvOrNull();
        RedisStore redis = RedisStore.fromEnvOrNull();

        // Inicializar SmartScheduler
        smartScheduler = new SmartScheduler(pendingTasks, workers, mqtt);

        // ---- HTTP ----
        int port = 8080;
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        // Health
        server.createContext("/api/health", ex -> HttpUtils.respond(ex, 200, "OK", "text/plain"));
        server.createContext("/api/health/mqtt", ex ->
                HttpUtils.respond(ex, 200, (mqtt != null && mqtt.isConnected()) ? "OK" : "DOWN", "text/plain"));
        server.createContext("/api/health/redis", ex ->
                HttpUtils.respond(ex, 200, (redis != null && redis.healthy()) ? "OK" : "DOWN", "text/plain"));

        // Workers
        server.createContext("/api/workers/register", new WorkersApi.RegisterHandler(workers, mqtt, redis));
        server.createContext("/api/workers/heartbeat", new WorkersApi.HeartbeatHandler(workers, mqtt));
        server.createContext("/api/workers", ex -> {
            // Handle CORS preflight requests
            if (HttpUtils.handleCorsPreflightRequest(ex)) {
                return;
            }
            
            if (!"GET".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }
            HttpUtils.respondJson(ex, 200, workers.values());
        });

        // Jobs
        server.createContext("/api/jobs", new JobsApi.SubmitHandler(jobs, smartScheduler, mqtt, redis));
        server.createContext("/api/jobs/status", new JobsApi.StatusHandler(jobs));
        server.createContext("/api/jobs/result", new JobsApi.ResultHandler(jobs));
        server.createContext("/api/jobs/debug", new JobsApi.DebugHandler(jobs));
        server.createContext("/api/jobs/scripts", new JobsApi.ScriptsHandler(jobs));

        // Tasks
        server.createContext("/api/tasks/next", new TasksApi.SmartNextHandler(jobs, smartScheduler));
        server.createContext("/api/tasks/complete", new TasksApi.SmartCompleteHandler(jobs, smartScheduler, mqtt, redis));

        // Scheduler stats
        server.createContext("/api/scheduler/stats", ex -> {
            // Handle CORS preflight requests
            if (HttpUtils.handleCorsPreflightRequest(ex)) {
                return;
            }
            
            if (!"GET".equals(ex.getRequestMethod())) {
                HttpUtils.respond(ex, 405, "", "");
                return;
            }
            HttpUtils.respondJson(ex, 200, smartScheduler.getSchedulerStats());
        });

        server.start();
        System.out.println("Road-Poneglyph HTTP listening on :8080");

        // ---- gRPC ----
        int grpcPort = Integer.parseInt(System.getenv().getOrDefault("GRPC_PORT", "50051"));
        Server grpcServer = ServerBuilder.forPort(grpcPort)
                .addService(new MasterService(
                        (ConcurrentMap<String, Worker>) workers,
                        (ConcurrentMap<String, JobCtx>) jobs,
                        pendingTasks,
                        smartScheduler,
                        mqtt,
                        redis))
                .build()
                .start();
        System.out.println("Road-Poneglyph gRPC listening on :" + grpcPort);

        // Graceful shutdown
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                grpcServer.shutdown();
            } catch (Exception ignored) {
            }
            try {
                if (mqtt != null) mqtt.close();
            } catch (Exception ignored) {
            }
            try {
                if (redis != null) redis.close();
            } catch (Exception ignored) {
            }
        }));

        grpcServer.awaitTermination(); // block process
    }
}
