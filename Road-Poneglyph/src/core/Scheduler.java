package core;

import model.JobCtx;
import model.Task;
import model.TaskType;
// import utils.S3Utils;

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
            // Store locally (existing functionality)
            File dir = new File("out");
            if (!dir.exists()) dir.mkdirs();
            File f = new File(dir, ctx.spec.job_id + ".txt");
            try (FileOutputStream fos = new FileOutputStream(f, false)) {
                fos.write(ctx.finalOutput.getBytes(StandardCharsets.UTF_8));
            }
            System.out.println("[RESULT STORED] " + f.getAbsolutePath());

            // Store in AWS S3 (commented out for testing)
            // storeResultInS3(ctx);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    /**
     * Store job result in AWS S3 using S3Utils.
     * This method is commented out for testing but ready to use.
     */
    /* 
    private static void storeResultInS3(JobCtx ctx) {
        try {
            S3Utils s3Utils = S3Utils.fromEnvironment();
            if (s3Utils == null) {
                System.out.println("[S3] S3 storage not configured - skipping S3 upload");
                return;
            }
            
            // Check if bucket is accessible before attempting upload
            if (!s3Utils.isBucketAccessible()) {
                System.err.println("[S3] Bucket not accessible - skipping S3 upload");
                return;
            }
            
            // Prepare metadata for the job result
            Map<String, String> metadata = new HashMap<>();
            metadata.put("job-type", "mapreduce");
            metadata.put("maps-completed", String.valueOf(ctx.completedMaps));
            metadata.put("reduces-completed", String.valueOf(ctx.completedReduces));
            metadata.put("final-output-size", String.valueOf(ctx.finalOutput.length()));
            
            // Store the result in S3
            String s3Key = s3Utils.storeJobResultWithMetadata(
                ctx.spec.job_id, 
                ctx.finalOutput, 
                metadata
            );
            
            System.out.println("[S3] Job result stored at: " + s3Key);
            
            // Optionally generate a presigned URL for temporary access (24 hours)
            String presignedUrl = s3Utils.generatePresignedUrl(s3Key, 24 * 60);
            if (presignedUrl != null) {
                System.out.println("[S3] Temporary access URL (24h): " + presignedUrl);
            }
            
            s3Utils.close();
            
        } catch (Exception e) {
            System.err.println("[S3 ERROR] Failed to store result in S3: " + e.getMessage());
            e.printStackTrace();
        }
    }
    */
}
