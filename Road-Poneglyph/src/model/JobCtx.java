package model;

import java.util.*;

public class JobCtx {
    public JobSpec spec;
    public JobState state = JobState.PENDING;

    public List<Task> mapTasks = new ArrayList<>();
    public Map<Integer, List<String>> partitionKV = new HashMap<>();
    public List<Task> reduceTasks = new ArrayList<>();

    public String finalOutput = "";
    public byte[] mapScript;
    public byte[] reduceScript;

    public int completedMaps = 0;
    public int completedReduces = 0;
}
