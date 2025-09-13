import os
import json
from typing import Callable, Optional
import threading

import paho.mqtt.client as mqtt


class MqttBridge:
    def __init__(self, on_message: Optional[Callable[[str, bytes], None]] = None):
        self.host = os.getenv("EMQX_HOST", "localhost")
        self.port = int(os.getenv("EMQX_PORT", "1883"))
        self.username = os.getenv("EMQX_USERNAME")
        self.password = os.getenv("EMQX_PASSWORD")
        self._on_message = on_message
        self._client = mqtt.Client()
        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_mqtt_message
        self._thread = None

    def start(self):
        try:
            self._client.connect(self.host, self.port, keepalive=60)
            # Subscribe to worker lifecycle topics
            self._client.subscribe("gridmr/workers/+/register")
            self._client.subscribe("gridmr/workers/+/heartbeat")
            self._client.subscribe("gridmr/results/+")
            self._thread = threading.Thread(target=self._client.loop_forever, daemon=True)
            self._thread.start()
            print(f"MqttBridge: connected to mqtt://{self.host}:{self.port}")
        except Exception as e:
            print(f"MqttBridge: MQTT connect failed ({e}). Continuing without broker.")

    def publish_task(self, worker_id: str, task: dict):
        topic = f"gridmr/tasks/{worker_id}"
        self._client.publish(topic, json.dumps(task), qos=1)

    def broadcast_task(self, task: dict):
        topic = "gridmr/tasks/broadcast"
        self._client.publish(topic, json.dumps(task), qos=1)

    # Callbacks
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MqttBridge: MQTT connected")
        else:
            print(f"MqttBridge: MQTT connection failed rc={rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        if self._on_message:
            self._on_message(msg.topic, msg.payload)
