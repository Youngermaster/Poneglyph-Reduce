import com.sun.net.httpserver.HttpServer;
import api.JobsApi;
import api.TasksApi;
import api.WorkersApi;
import core.Scheduler;
import http.HttpUtils;
import model.JobCtx;
import model.Task;
import model.Worker;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.*;

public class Main {

    // Shared in-memory state (can be swapped for persistent stores later)
    private static final Map<String, Worker> workers = new ConcurrentHashMap<>();
    private static final Map<String, JobCtx> jobs = new ConcurrentHashMap<>();
    private static final BlockingQueue<Task> pendingTasks = new LinkedBlockingQueue<>();
    private static final Scheduler scheduler = new Scheduler(pendingTasks);

    public static void main(String[] args) throws Exception {
        int port = 8080;
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        // Health
        server.createContext("/api/health", ex -> HttpUtils.respond(ex, 200, "OK", "text/plain"));

        // Workers
        server.createContext("/api/workers/register", new WorkersApi.RegisterHandler(workers));

        // Jobs (submit, status, result, debug, scripts)
        server.createContext("/api/jobs", new JobsApi.SubmitHandler(jobs, scheduler));
        server.createContext("/api/jobs/status", new JobsApi.StatusHandler(jobs));
        server.createContext("/api/jobs/result", new JobsApi.ResultHandler(jobs));
        server.createContext("/api/jobs/debug", new JobsApi.DebugHandler(jobs));
        server.createContext("/api/jobs/scripts", new JobsApi.ScriptsHandler(jobs));

        // Tasks (next/complete)
        server.createContext("/api/tasks/next", new TasksApi.NextHandler(jobs, pendingTasks));
        server.createContext("/api/tasks/complete", new TasksApi.CompleteHandler(jobs, scheduler));

        server.start();
        System.out.println("Road-Poneglyph Master listening on :8080");
    }
}
