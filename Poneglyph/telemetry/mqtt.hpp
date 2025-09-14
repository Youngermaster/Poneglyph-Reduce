#pragma once
#include <memory>
#include <string>
#include <mqtt/async_client.h>

namespace telemetry {
    // Simple RAII MQTT publisher with background reconnect.
    class MqttClientManager {
    public:
        // Creates the client if MQTT_BROKER is set; otherwise returns nullptr.
        static std::unique_ptr<MqttClientManager> from_env_or_null();

        ~MqttClientManager();

        bool is_connected() const;

        void publish_json(const std::string &topic, const std::string &json);

    private:
        MqttClientManager(std::string broker, std::string username, std::string password);

        void try_connect_once();

        void start_background_reconnect();

        std::string broker_;
        std::string username_;
        std::string password_;

        std::unique_ptr<mqtt::async_client> client_;
        mqtt::connect_options conn_opts_;
    };
} // namespace telemetry
