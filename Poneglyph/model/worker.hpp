#pragma once
#include <memory>
#include <string>

namespace telemetry {
    class MqttClientManager;
}

class Worker {
public:
    explicit Worker(std::string masterUrl,
                    std::unique_ptr<telemetry::MqttClientManager> mqtt = nullptr);

    int run(); // main loop

private:
    std::string master;
    std::string workerId;

    std::unique_ptr<telemetry::MqttClientManager> mqtt;

    void registerSelf();

    void startHeartbeat();

    static long long now_ms();

    std::pair<double, double> getSystemMetrics();

    void handleMap(const std::string &taskJson);

    void handleReduce(const std::string &taskJson);
};
