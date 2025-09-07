package core;

public final class Partitioner {
    private Partitioner() {
    }

    public static int partitionOf(String key, int reducers) {
        return Math.floorMod(key.hashCode(), reducers);
    }
}
