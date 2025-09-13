import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import java.util.concurrent.TimeUnit;
import com.poneglyph.grpc.PoneglyphProto.*; // generated classes (after protoc)
import com.poneglyph.grpc.WorkerManagementServiceGrpc;
import com.poneglyph.grpc.JobManagementServiceGrpc;

public class Demo {
    public static void main(String[] args) throws Exception {
        String host = System.getenv().getOrDefault("GRPC_HOST", "localhost");
        int port = Integer.parseInt(System.getenv().getOrDefault("GRPC_PORT", "50051"));

        ManagedChannel channel = ManagedChannelBuilder.forAddress(host, port)
                .usePlaintext()
                .build();

        JobManagementServiceGrpc.JobManagementServiceBlockingStub jobs = JobManagementServiceGrpc.newBlockingStub(channel);
        WorkerManagementServiceGrpc.WorkerManagementServiceBlockingStub workers = WorkerManagementServiceGrpc.newBlockingStub(channel);

        System.out.println("=== PONEGLYPH gRPC QUICK DEMO ===");
        System.out.println("Middleware: " + host + ":" + port);

        // Register a worker (simulate master owned worker)
        RegisterWorkerResponse reg = workers.registerWorker(RegisterWorkerRequest.newBuilder()
                .setWorkerName("java-master-proxy")
                .setCapacity(1)
                .addCapabilities("MAP")
                .addCapabilities("REDUCE")
                .setLocation("us-east-1")
                .build());
        System.out.println("Registered workerId=" + reg.getWorkerId());

        // Submit a job
        String jobId = "job-demo-java";
        SubmitJobResponse submit = jobs.submitJob(SubmitJobRequest.newBuilder()
                .setJobId(jobId)
                .setInputText("hello poneglyph hello gridmr from java")
                .setSplitSize(1)
                .setReducers(0)
                .build());
        System.out.println("Submit status=" + submit.getSuccess() + " id=" + submit.getJobId());

        // Poll status
        for (int i = 0; i < 5; i++) {
            JobStatusResponse status = jobs.getJobStatus(JobStatusRequest.newBuilder().setJobId(jobId).build());
            System.out.println("Iteration " + i + " jobState=" + status.getState() + " progress=" + status.getProgressPercentage());
            Thread.sleep(1000);
        }

        channel.shutdownNow().awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("Done.");
    }
}
