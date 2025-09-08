package grpc;

import helloworld.GreeterGrpc;
import helloworld.HelloWorldProto.HelloReply;
import helloworld.HelloWorldProto.HelloRequest;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public class gRPCUtils {
    public static void main(String[] args) {
        ManagedChannel channel = ManagedChannelBuilder.forAddress("localhost", 50051)
                .usePlaintext()
                .build();

        GreeterGrpc.GreeterBlockingStub stub = GreeterGrpc.newBlockingStub(channel);

        HelloRequest request = HelloRequest.newBuilder().setName("Camilo").build();
        HelloReply response = stub.sayHello(request);

        System.out.println("Respuesta del servidor: " + response.getMessage());

        channel.shutdown();
    }
}
