import { useEffect, useState, useCallback } from "react";
import mqtt from "mqtt";
import type { MqttClient } from "mqtt";
import type { MqttMessage, JobProgress, WorkerNode } from "@/types/mqtt";

interface UseMqttReturn {
  isConnected: boolean;
  jobs: Map<string, JobProgress>;
  workers: Map<string, WorkerNode>;
  recentMessages: MqttMessage[];
  error: string | null;
}

export const useMqtt = (): UseMqttReturn => {
  const [, setClient] = useState<MqttClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [jobs, setJobs] = useState<Map<string, JobProgress>>(new Map());
  const [workers] = useState<Map<string, WorkerNode>>(new Map());
  const [recentMessages, setRecentMessages] = useState<MqttMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const addMessage = useCallback((message: MqttMessage) => {
    setRecentMessages((prev) => {
      const newMessages = [message, ...prev].slice(0, 100); // Keep last 100 messages
      return newMessages;
    });
  }, []);

  const updateJob = useCallback(
    (jobId: string, updates: Partial<JobProgress>) => {
      setJobs((prev) => {
        const newJobs = new Map(prev);
        const existing = newJobs.get(jobId);
        if (existing) {
          newJobs.set(jobId, { ...existing, ...updates });
        } else {
          newJobs.set(jobId, {
            jobId,
            totalMaps: 0,
            completedMaps: 0,
            totalReduces: 0,
            completedReduces: 0,
            state: "PENDING",
            startTime: Date.now(),
            ...updates,
          });
        }
        return newJobs;
      });
    },
    []
  );

  useEffect(() => {
    // Use environment variables with fallbacks for development
    const mqttHost = import.meta.env.VITE_MQTT_HOST || "localhost";
    const mqttPort = import.meta.env.VITE_MQTT_PORT || "8083";

    const mqttClient = mqtt.connect(`ws://${mqttHost}:${mqttPort}/mqtt`);

    mqttClient.on("connect", () => {
      console.log("Connected to MQTT broker");
      setIsConnected(true);
      setError(null);

      // Subscribe to all gridmr topics
      mqttClient.subscribe("gridmr/#", (err) => {
        if (err) {
          console.error("Failed to subscribe:", err);
          setError("Failed to subscribe to MQTT topics");
        }
      });
    });

    mqttClient.on("error", (err) => {
      console.error("MQTT connection error:", err);
      setError(`MQTT connection error: ${err.message}`);
      setIsConnected(false);
    });

    mqttClient.on("close", () => {
      console.log("MQTT connection closed");
      setIsConnected(false);
    });

    mqttClient.on("message", (topic, message) => {
      try {
        const data = JSON.parse(message.toString());
        const topicParts = topic.split("/");

        if (topicParts[0] !== "gridmr") return;

        if (topicParts[1] === "job") {
          if (topicParts[2] === "created") {
            const mqttMessage: MqttMessage = { type: "job/created", data };
            addMessage(mqttMessage);
            updateJob(data.jobId, {
              totalMaps: data.maps,
              totalReduces: data.reducers,
              state: "RUNNING",
              startTime: data.ts,
            });
          } else if (topicParts.length >= 4) {
            const jobId = topicParts[2];
            const eventType = topicParts[3];
            const subType = topicParts[4];

            if (eventType === "map" && subType === "completed") {
              const mqttMessage: MqttMessage = { type: "map/completed", data };
              addMessage(mqttMessage);
              updateJob(jobId, {
                completedMaps: data.mapsCompleted,
              });
            } else if (eventType === "reduce" && subType === "completed") {
              const mqttMessage: MqttMessage = {
                type: "reduce/completed",
                data,
              };
              addMessage(mqttMessage);
              updateJob(jobId, {
                completedReduces: data.reducesCompleted,
              });
            } else if (eventType === "shuffle" && subType === "partitions") {
              const mqttMessage: MqttMessage = {
                type: "shuffle/partitions",
                data,
              };
              addMessage(mqttMessage);
            } else if (eventType === "state") {
              const mqttMessage: MqttMessage = { type: "job/state", data };
              addMessage(mqttMessage);
              updateJob(jobId, {
                state: data.state,
                endTime:
                  data.state === "SUCCEEDED" || data.state === "FAILED"
                    ? data.ts
                    : undefined,
              });
            }
          }
        }
      } catch (err) {
        console.error("Error parsing MQTT message:", err);
        setError(
          `Error parsing message: ${
            err instanceof Error ? err.message : "Unknown error"
          }`
        );
      }
    });

    setClient(mqttClient);

    return () => {
      if (mqttClient) {
        mqttClient.end();
      }
    };
  }, [addMessage, updateJob]);

  return {
    isConnected,
    jobs,
    workers,
    recentMessages,
    error,
  };
};
