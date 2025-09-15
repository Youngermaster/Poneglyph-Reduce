#pragma once
#include <memory>
#include <string>

namespace telemetry {
    class MqttClientManager;
}

class MasterGrpcClient; // fwd

class Worker {
public:
    explicit Worker(std::string masterUrl,
                    std::unique_ptr<telemetry::MqttClientManager> mqtt = nullptr,
                    std::unique_ptr<MasterGrpcClient> grpc = nullptr);

    int run();

private:
    std::string master; // HTTP base (e.g., http://master:8080)
    std::string workerId;

    std::unique_ptr<telemetry::MqttClientManager> mqtt;
    std::unique_ptr<MasterGrpcClient> grpc; // if present, use gRPC

    void registerSelf();

    void startHeartbeat();

    static long long now_ms();

    std::pair<double, double> getSystemMetrics();

    // HTTP paths (existing)
    void handleMap(const std::string &taskJson);

    void handleReduce(const std::string &taskJson);

    // gRPC paths
    void handleMapGrpc(const gridmr::MapTask &mt);

    void handleReduceGrpc(const gridmr::ReduceTask &rt);
};
