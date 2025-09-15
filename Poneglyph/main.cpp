#include "model/worker.hpp"
#include "telemetry/mqtt.hpp"
#include "rpc/grpc_client.hpp"

#include <cstdlib>
#include <memory>
#include <string>

static std::string getenv_or(const char *k, const char *dflt) {
    const char *v = std::getenv(k);
    return v ? std::string(v) : std::string(dflt);
}

int main() {
    std::string master_http = getenv_or("PONEGLYPH_MASTER_URL", "http://master:8080");
    auto mqtt = telemetry::MqttClientManager::from_env_or_null();

    std::unique_ptr<MasterGrpcClient> grpcClient;
    const std::string use_grpc = getenv_or("PONEGLYPH_USE_GRPC", "0");
    if (use_grpc == "1" || use_grpc == "true" || use_grpc == "TRUE") {
        std::string grpc_addr = getenv_or("PONEGLYPH_MASTER_GRPC", "master:50051");
        grpcClient = std::make_unique<MasterGrpcClient>(grpc_addr);
    }

    Worker w(master_http, std::move(mqtt), std::move(grpcClient));
    return w.run();
}
