FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl python3 ca-certificates \
    git libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Build and install Paho MQTT C library
WORKDIR /usr/src
RUN git clone https://github.com/eclipse/paho.mqtt.c.git && \
    cd paho.mqtt.c && \
    cmake -Bbuild -H. -DPAHO_WITH_SSL=TRUE -DPAHO_BUILD_DOCUMENTATION=FALSE -DPAHO_BUILD_SAMPLES=FALSE && \
    cmake --build build/ --target install && \
    ldconfig && \
    cd .. && rm -rf paho.mqtt.c

# Build and install Paho MQTT C++ library
RUN git clone https://github.com/eclipse/paho.mqtt.cpp.git && \
    cd paho.mqtt.cpp && \
    cmake -Bbuild -H. -DPAHO_WITH_SSL=TRUE -DPAHO_BUILD_DOCUMENTATION=FALSE -DPAHO_BUILD_SAMPLES=FALSE && \
    cmake --build build/ --target install && \
    ldconfig && \
    cd .. && rm -rf paho.mqtt.cpp

WORKDIR /app
COPY . /app

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j

ENV PONEGLYPH_MASTER_URL=http://master:8080
# Optional MQTT envs; compose will override
# ENV MQTT_BROKER=tcp://mqtt:1883 MQTT_USERNAME=admin MQTT_PASSWORD=public

CMD ["./build/Poneglyph"]
