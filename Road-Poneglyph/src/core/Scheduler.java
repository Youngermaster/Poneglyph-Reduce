package core;

import model.JobCtx;
import model.Task;
import model.TaskType;

import java.nio.charset.StandardCharsets;
import java.io.File;
import java.io.FileOutputStream;
import java.util.*;
import java.util.concurrent.BlockingQueue;

/**
 * Very small FIFO scheduler. Evolve it to use capacity/heartbeats/timeouts.
 */
public class Scheduler {
    private final BlockingQueue<Task> pending;

    public Scheduler(BlockingQueue<Task> pending) {
        this.pending = pending;
    }

    public void enqueueAll(List<Task> tasks) {
        for (Task t : tasks) pending.offer(t);
    }

    public void enqueue(Task t) {
        pending.offer(t);
    }

    /**
     * Build MAP tasks by line-aware splitting.
     */
    public List<Task> buildMapTasks(String jobId, String inputText, int splitSize) {
        List<Task> out = new ArrayList<>();
        List<String> lines = Arrays.asList(
                Optional.ofNullable(inputText).orElse("").split("\n", -1)
        );
        StringBuilder chunk = new StringBuilder();
        int currentSize = 0;
        int t = 0;
        for (String ln : lines) {
            String l = ln + "\n";
            if (currentSize + l.length() > splitSize && currentSize > 0) {
                Task mt = new Task();
                mt.type = TaskType.MAP;
                mt.taskId = "map-" + (t++);
                mt.jobId = jobId;
                mt.inputChunk = chunk.toString();
                out.add(mt);
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
            mt.jobId = jobId;
            mt.inputChunk = chunk.toString();
            out.add(mt);
        }
        return out;
    }

    /**
     * Persist final output as our "local S3 sink".
     */
    public static void persistResult(JobCtx ctx) {
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
}
