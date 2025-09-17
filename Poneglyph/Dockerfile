FROM debian:bookworm-slim

# Install pre-built packages (much faster than building from source!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl python3 ca-certificates git \
    libgrpc++-dev libgrpc-dev libprotobuf-dev protobuf-compiler-grpc \
    protobuf-compiler libssl-dev pkg-config \
    libpaho-mqtt-dev libpaho-mqttpp-dev \
 && rm -rf /var/lib/apt/lists/*

# --- Build worker ---
WORKDIR /app
COPY . /app
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j

# Defaults
ENV PONEGLYPH_MASTER_URL=http://master:8080
ENV PONEGLYPH_USE_GRPC=1
ENV PONEGLYPH_MASTER_GRPC=master:50051
CMD ["./build/Poneglyph"]
