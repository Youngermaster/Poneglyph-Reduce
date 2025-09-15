package store;

import com.google.gson.Gson;
import model.JobCtx;
import model.JobSpec;
import model.Worker;
import redis.clients.jedis.JedisPooled;

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
    }

    @Override
    public void close() {
        try {
            if (jedis != null) jedis.close();
        } catch (Exception ignored) {
        }
    }
}
