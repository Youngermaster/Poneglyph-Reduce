package store;

import com.google.gson.Gson;
import model.JobCtx;
import model.JobSpec;
import model.Worker;
import redis.clients.jedis.JedisPooled;
import utils.S3Utils;

import java.util.List;
import java.util.Map;

public final class RedisStore implements AutoCloseable {
    private static final Gson GSON = new Gson();

    private final JedisPooled jedis;

    private RedisStore(String url) {
        this.jedis = new JedisPooled(url);
    }

    public static RedisStore fromEnvOrNull() {
        try {
            String url = System.getenv().getOrDefault("REDIS_URL", "");
            if (url.isBlank()) return null;
            return new RedisStore(url);
        } catch (Exception e) {
            e.printStackTrace();
            return null; // run without Redis if not available
        }
    }

    public boolean healthy() {
        try {
            return "PONG".equalsIgnoreCase(jedis.ping());
        } catch (Exception e) {
            return false;
        }
    }

    // --- Workers ---
    public void saveWorker(Worker w) {
        if (jedis == null) return;
        String key = "gridmr:workers:" + w.workerId;
        jedis.hset(key, Map.of(
                "workerId", w.workerId,
                "name", w.name,
                "capacity", String.valueOf(w.capacity),
                "lastHeartbeat", String.valueOf(w.lastHeartbeat)
        ));
    }

    // --- Jobs ---
    public void saveJobSpec(JobSpec spec) {
        if (jedis == null) return;
        jedis.set("gridmr:jobs:" + spec.job_id + ":spec", GSON.toJson(spec));
    }

    public void saveJobCounters(String jobId, int mapsCompleted, int reducesCompleted) {
        if (jedis == null) return;
        String key = "gridmr:jobs:" + jobId + ":counters";
        jedis.hset(key, Map.of(
                "maps_completed", String.valueOf(mapsCompleted),
                "reduces_completed", String.valueOf(reducesCompleted)
        ));
    }

    public void savePartitionSizes(String jobId, List<Integer> sizes) {
        if (jedis == null) return;
        jedis.set("gridmr:jobs:" + jobId + ":partitions", GSON.toJson(sizes));
    }

    public void setJobState(String jobId, String state) {
        if (jedis == null) return;
        jedis.set("gridmr:jobs:" + jobId + ":state", state);
    }

    public void storeFinalResult(String jobId, String output) {
        if (jedis == null) return;
        jedis.set("gridmr:jobs:" + jobId + ":result", output);

        // Also store in S3
        storeResultInS3(jobId, output);
    }

    /**
     * Store job result in AWS S3 with Redis metadata.
     */
    private void storeResultInS3(String jobId, String output) {
        try {
            S3Utils s3Utils = S3Utils.fromEnvironment();
            if (s3Utils == null) {
                System.out.println("[REDIS-S3] S3 storage not configured - skipping S3 upload");
                return;
            }
            
            if (!s3Utils.isBucketAccessible()) {
                System.err.println("[REDIS-S3] Bucket not accessible - skipping S3 upload");
                return;
            }
            
            // Retrieve additional metadata from Redis
            Map<String, String> metadata = new java.util.HashMap<>();
            metadata.put("storage-source", "redis-store");
            metadata.put("stored-timestamp", String.valueOf(System.currentTimeMillis()));
            
            // Get job counters if available
            String countersKey = "gridmr:jobs:" + jobId + ":counters";
            Map<String, String> counters = jedis.hgetAll(countersKey);
            if (counters != null && !counters.isEmpty()) {
                metadata.put("maps-completed", counters.getOrDefault("maps_completed", "0"));
                metadata.put("reduces-completed", counters.getOrDefault("reduces_completed", "0"));
            }
            
            // Get job state if available
            String state = jedis.get("gridmr:jobs:" + jobId + ":state");
            if (state != null) {
                metadata.put("job-state", state);
            }
            
            // Store the result in S3
            String s3Key = s3Utils.storeJobResultWithMetadata(jobId, output, metadata);
            
            // Store S3 location back in Redis for reference
            jedis.set("gridmr:jobs:" + jobId + ":s3_location", s3Key);
            
            System.out.println("[REDIS-S3] Job result stored at S3: " + s3Key);
            
            s3Utils.close();
            
        } catch (Exception e) {
            System.err.println("[REDIS-S3 ERROR] Failed to store result in S3: " + e.getMessage());
        }
    }
    @Override
    public void close() {
        try {
            if (jedis != null) jedis.close();
        } catch (Exception ignored) {
        }
    }
}
