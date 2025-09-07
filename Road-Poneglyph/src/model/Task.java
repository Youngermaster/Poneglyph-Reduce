package model;

import java.util.ArrayList;
import java.util.List;

public class Task {
    public String taskId;
    public String jobId;
    public TaskType type;

    // MAP
    public String inputChunk;

    // REDUCE
    public int partitionIndex;
    public List<String> kvLinesForReduce = new ArrayList<>();
}
