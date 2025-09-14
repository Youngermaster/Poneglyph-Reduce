FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl python3 ca-certificates \
    libpaho-mqttpp3-dev libpaho-mqtt-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j

ENV PONEGLYPH_MASTER_URL=http://master:8080
# Optional MQTT envs; compose will override
# ENV MQTT_BROKER=tcp://mqtt:1883 MQTT_USERNAME=admin MQTT_PASSWORD=public

CMD ["./build/Poneglyph"]
