#include "mqtt.hpp"
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

using namespace std::chrono_literals;

namespace telemetry {
    static std::string getenv_or_empty(const char *k) {
        const char *v = std::getenv(k);
        return v ? std::string(v) : std::string{};
    }

    std::unique_ptr<MqttClientManager> MqttClientManager::from_env_or_null() {
        auto broker = getenv_or_empty("MQTT_BROKER");
        if (broker.empty()) return nullptr;
        return std::unique_ptr<MqttClientManager>(
            new MqttClientManager(std::move(broker),
                                  getenv_or_empty("MQTT_USERNAME"),
                                  getenv_or_empty("MQTT_PASSWORD")));
    }

    MqttClientManager::MqttClientManager(std::string broker, std::string username, std::string password)
        : broker_(std::move(broker)), username_(std::move(username)), password_(std::move(password)) {
        client_ = std::make_unique<mqtt::async_client>(broker_, "poneglyph-worker-" + std::to_string(std::rand()));

        conn_opts_.set_clean_session(true);
        if (!username_.empty()) {
            conn_opts_.set_user_name(username_);
            conn_opts_.set_password(password_);
        }
        // Automatic reconnect (after a successful connect). We still run a background
        // thread to get the *first* connect established.
        conn_opts_.set_automatic_reconnect(true);

        try_connect_once();
        if (!is_connected()) start_background_reconnect();
    }

    void MqttClientManager::try_connect_once() {
        try {
            auto tok = client_->connect(conn_opts_);
            tok->wait();
            std::cout << "[MQTT/C++] Connected to " << broker_ << std::endl;
        } catch (const std::exception &e) {
            std::cout << "[MQTT/C++] Initial connect failed: " << e.what() << std::endl;
        }
    }

    void MqttClientManager::start_background_reconnect() {
        std::thread([this] {
            int delay_ms = 1000;
            while (!is_connected()) {
                try {
                    auto tok = client_->connect(conn_opts_);
                    tok->wait();
                    std::cout << "[MQTT/C++] Connected to " << broker_ << " (after retries)" << std::endl;
                    break;
                } catch (const std::exception &e) {
                    std::cout << "[MQTT/C++] Reconnect failed: " << e.what()
                            << " – retrying in " << delay_ms << "ms" << std::endl;
                    std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                    delay_ms = std::min(delay_ms * 2, 30'000);
                }
            }
        }).detach();
    }

    bool MqttClientManager::is_connected() const {
        return client_ && client_->is_connected();
    }

    void MqttClientManager::publish_json(const std::string &topic, const std::string &json) {
        if (!is_connected()) {
            std::cout << "[MQTT/C++] Not connected. Dropping publish to " << topic << std::endl;
            return;
        }
        try {
            // QoS 0, non-retained to match Java
            client_->publish(topic, json.c_str(), json.size(), 0, false);
        } catch (const std::exception &e) {
            std::cout << "[MQTT/C++] Publish failed: " << e.what() << std::endl;
        }
    }

    MqttClientManager::~MqttClientManager() {
        try {
            if (client_ && client_->is_connected()) client_->disconnect()->wait();
        } catch (...) {
        }
    }
} // namespace telemetry
