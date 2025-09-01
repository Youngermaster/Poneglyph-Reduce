FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake curl python3 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Generador por defecto: Unix Makefiles (usa 'make')
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j

# el master se verá como 'master' por el nombre del servicio en compose
ENV PONEGLYPH_MASTER_URL=http://master:8080
CMD ["./build/Poneglyph"]
