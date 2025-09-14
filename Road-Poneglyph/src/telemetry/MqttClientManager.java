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

    private MqttClientManager(String broker, String username, String password) throws MqttException {
        this.broker = broker;
        this.username = username;
        this.password = password;
        this.client = new MqttClient(broker, "road-poneglyph-" + UUID.randomUUID());
        MqttConnectOptions opts = new MqttConnectOptions();
        if (username != null && !username.isBlank()) {
            opts.setUserName(username);
            if (password != null) opts.setPassword(password.toCharArray());
        }
        opts.setAutomaticReconnect(true);
        opts.setCleanSession(true);
        client.connect(opts);
    }

    public static MqttClientManager fromEnvOrNull() {
        try {
            String broker = System.getenv().getOrDefault("MQTT_BROKER", "");
            if (broker.isBlank()) return null;
            String user = System.getenv("MQTT_USERNAME");
            String pass = System.getenv("MQTT_PASSWORD");
            return new MqttClientManager(broker, user, pass);
        } catch (Exception e) {
            e.printStackTrace();
            return null; // run without MQTT if broker not available
        }
    }

    public void publishJson(String topic, Object payload) {
        if (!isConnected()) return;
        try {
            byte[] bytes = GSON.toJson(payload).getBytes(StandardCharsets.UTF_8);
            MqttMessage msg = new MqttMessage(bytes);
            msg.setQos(0);
            client.publish(topic, msg);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public boolean isConnected() {
        return client != null && client.isConnected();
    }

    @Override public void close() {
        try { if (client != null && client.isConnected()) client.disconnect(); }
        catch (Exception ignored) {}
        try { if (client != null) client.close(); }
        catch (Exception ignored) {}
    }
}
