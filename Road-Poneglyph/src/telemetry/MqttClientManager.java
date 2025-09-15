package telemetry;

import com.google.gson.Gson;
import org.eclipse.paho.client.mqttv3.*;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;

public final class MqttClientManager implements AutoCloseable {
    private static final Gson GSON = new Gson();

    private final String broker;
    private final String username;
    private final String password;
    private final MqttClient client;
    private final MqttConnectOptions opts;

    private MqttClientManager(String broker, String username, String password) {
        this.broker = broker;
        this.username = username;
        this.password = password;

        MqttClient tmpClient;
        try {
            tmpClient = new MqttClient(broker, "road-poneglyph-" + UUID.randomUUID());
        } catch (MqttException e) {
            // Extremely rare (bad URI). Log and rethrow as runtime to surface the issue early.
            throw new RuntimeException("MQTT init failed for broker=" + broker, e);
        }
        this.client = tmpClient;

        this.opts = new MqttConnectOptions();
        if (username != null && !username.isBlank()) {
            opts.setUserName(username);
            if (password != null) opts.setPassword(password.toCharArray());
        }
        opts.setCleanSession(true);
        opts.setAutomaticReconnect(true); // only takes effect *after* a successful connect

        // Try to connect once, then background-retry until success.
        try {
            client.connect(opts);
            System.out.println("[MQTT] Connected to " + broker);
        } catch (Exception first) {
            System.out.println("[MQTT] Initial connect failed (" + first.getMessage() + "). Will retry in background.");
            startBackgroundReconnect();
        }
    }

    public static MqttClientManager fromEnvOrNull() {
        String broker = System.getenv().getOrDefault("MQTT_BROKER", "");
        if (broker.isBlank()) return null;
        String user = System.getenv("MQTT_USERNAME");
        String pass = System.getenv("MQTT_PASSWORD");
        return new MqttClientManager(broker, user, pass); // constructor handles retry internally
    }

    private void startBackgroundReconnect() {
        Thread t = new Thread(() -> {
            int delayMs = 1000;
            while (!client.isConnected()) {
                try {
                    client.connect(opts);
                    System.out.println("[MQTT] Connected to " + broker + " (after retries)");
                    break;
                } catch (Exception e) {
                    System.out.println("[MQTT] Reconnect failed: " + e.getMessage() + " – retrying in " + delayMs + "ms");
                    try {
                        Thread.sleep(delayMs);
                    } catch (InterruptedException ignored) {
                    }
                    delayMs = Math.min(delayMs * 2, 30_000);
                }
            }
        }, "mqtt-reconnector");
        t.setDaemon(true);
        t.start();
    }

    public boolean isConnected() {
        return client != null && client.isConnected();
    }

    public void publishJson(String topic, Object payload) {
        if (!isConnected()) {
            System.out.println("[MQTT] Not connected. Dropping publish to " + topic);
            return;
        }
        try {
            byte[] bytes = GSON.toJson(payload).getBytes(StandardCharsets.UTF_8);
            MqttMessage msg = new MqttMessage(bytes);
            msg.setQos(0);
            client.publish(topic, msg);
        } catch (Exception e) {
            System.out.println("[MQTT] Publish failed: " + e.getMessage());
        }
    }

    @Override
    public void close() {
        try {
            if (client != null && client.isConnected()) client.disconnect();
        } catch (Exception ignored) {
        }
        try {
            if (client != null) client.close();
        } catch (Exception ignored) {
        }
    }
}
