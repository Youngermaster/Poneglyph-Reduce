FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl python3 ca-certificates git \
    autoconf libtool pkg-config libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# --- Build & install gRPC + Protobuf (local) ---
WORKDIR /usr/src
RUN git clone --recurse-submodules -b v1.74.0 --depth 1 --shallow-submodules https://github.com/grpc/grpc
WORKDIR /usr/src/grpc
RUN mkdir -p cmake/build && cd cmake/build && \
    cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_CXX_STANDARD=20 -DCMAKE_INSTALL_PREFIX=/usr/local ../.. && \
    make -j4 && make install && ldconfig
WORKDIR /usr/src
RUN rm -rf grpc

# --- Paho MQTT (as you already had) ---
RUN git clone https://github.com/eclipse/paho.mqtt.c.git && \
    cd paho.mqtt.c && \
    cmake -Bbuild -H. -DPAHO_WITH_SSL=TRUE -DPAHO_BUILD_DOCUMENTATION=FALSE -DPAHO_BUILD_SAMPLES=FALSE && \
    cmake --build build/ --target install && ldconfig && cd .. && rm -rf paho.mqtt.c

RUN git clone https://github.com/eclipse/paho.mqtt.cpp.git && \
    cd paho.mqtt.cpp && \
    cmake -Bbuild -H. -DPAHO_WITH_SSL=TRUE -DPAHO_BUILD_DOCUMENTATION=FALSE -DPAHO_BUILD_SAMPLES=FALSE && \
    cmake --build build/ --target install && ldconfig && cd .. && rm -rf paho.mqtt.cpp

# --- Build worker ---
WORKDIR /app
COPY . /app
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j

# Defaults
ENV PONEGLYPH_MASTER_URL=http://master:8080
ENV PONEGLYPH_USE_GRPC=1
ENV PONEGLYPH_MASTER_GRPC=master:50051
CMD ["./build/Poneglyph"]
