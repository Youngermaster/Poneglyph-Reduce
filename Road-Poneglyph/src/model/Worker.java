package model;

public class Worker {
    public String workerId;
    public String name;
    public int capacity;
    public long lastHeartbeat = System.currentTimeMillis();
}
