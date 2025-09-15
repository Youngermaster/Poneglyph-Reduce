#include "model/worker.hpp"
#include "telemetry/mqtt.hpp"
#include <cstdlib>
#include <string>
#include <memory>

int main() {
    std::string master = std::getenv("PONEGLYPH_MASTER_URL")
                             ? std::getenv("PONEGLYPH_MASTER_URL")
                             : "http://localhost:8080";
    auto mqtt = telemetry::MqttClientManager::from_env_or_null();
    Worker w(master, std::move(mqtt));
    return w.run();
}
