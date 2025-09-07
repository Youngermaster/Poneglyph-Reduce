package model;

/**
 * Client-submitted MapReduce program and config
 */
public class JobSpec {
    public String job_id;
    public String input_text;
    public Integer split_size;
    public Integer reducers;
    public String format;
    public String map_script_b64;
    public String reduce_script_b64;
}
