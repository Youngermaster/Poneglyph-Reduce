# Poneglyph Reduce

**Poneglyph Reduce** is a minimal-yet-real MapReduce system inspired by Hadoop/Spark and designed to satisfy the **GridMR** assignment requirements: a **Master-Workers** architecture running over the network (HTTP), job submission from a client, input splitting, scheduling, shuffle, reduce, and result consolidation. &#x20;

> ⚓ **One Piece-themed naming**
>
> * **Road-Poneglyph** (Master, Java): like the four “Road Poneglyphs” that lead to Laugh Tale—the coordinator that knows how to reach the final answer.
> * **Poneglyph** (Workers, C++): “regular” Poneglyphs that carry fragments of information—our agents that process shards and produce intermediate knowledge.
> * **Clover** (Client, Python): inspired by Professor Clover from Ohara—the one who can *read* and *submit* tasks, interacting with Poneglyphs to reveal the final story.

## 1) What is this project?

This repository implements a distributed data processing service—**Grid-style MapReduce**—over a set of heterogeneous nodes, with **HTTP/REST** communication, containerized nodes, and a simple Python client for job submission and validation. It follows the GridMR brief: design the system, define protocols, plan tasks (split/schedule/shuffle/reduce), and consolidate results for the client.  &#x20;

**Supported “user projects” (by writing custom map/reduce):** distributed statistics, inverted index, PageRank, simple ML (regression/clustering), Monte Carlo, cellular automata, etc.&#x20;

## 2) Architecture (high level)

* **Master (Road-Poneglyph / Java 17+)**

  * Accepts jobs from the client (Python), stores scripts and config.
  * Splits the input into **shards**, enqueues **MAP** tasks to workers, performs **shuffle** (group by key → partition), emits **REDUCE** tasks, and **consolidates** the outputs. &#x20;
* **Workers (Poneglyph / C++20)**

  * Register and **poll** the master for tasks.
  * Execute **map** on assigned shard (with a lightweight combiner), then consume partitions for **reduce** and return the reduced results.
* **Client (Clover / Python)**

  * Submits jobs containing **map()/reduce()** code, **split size**, **#reducers**, and **input location/content**; tracks status and fetches results.&#x20;

**Transport:** HTTP/REST for v1 (permitted GridMR suggestion). gRPC/WebSockets/MOM can be added later.&#x20;

**Deployment:** each node runs natively or in **Docker containers**; containers can live on different machines and expose APIs over the Internet (as per spec).&#x20;

## 3) How it works (MapReduce flow)

1. **Submit**: Clover sends a **Job Package** → `{ job_id, input_text|input_uri, split_size, reducers, format, map_script_b64, reduce_script_b64 }`.&#x20;
2. **Split & Schedule**: Road-Poneglyph splits the input and schedules **MAP** tasks to available workers (capacity, availability, load balancing are in-scope in the spec; v1 uses FIFO/availability).&#x20;
3. **Map**: Workers run `map.py` on their shard and return lines like `key\tvalue`.
4. **Shuffle**: Master partitions by `hash(key) % reducers`, grouping intermediate KV per reducer index.
5. **Reduce**: Master issues **REDUCE** tasks; workers run `reduce.py` over the grouped KVs, returning aggregated results.
6. **Consolidate**: Master concatenates reducer outputs (or persists them) and exposes the final result to the client.&#x20;

> **Data access modes (spec guidance):** GridMR allows either **transfer-based** modes (send/receive files) or via an API to a distributed store (**GridFS/S3-like**). This repo starts with transfer-based HTTP + local files, but the code is structured to add a storage API later (e.g., MinIO). &#x20;

## 4) Repository layout

```
Poneglyph-Reduce/
├─ Road-Poneglyph/     # Master (Java 17+, HTTP/REST)
│  ├─ src/...          # Master HTTP server, task planner, shuffle/consolidation
│  ├─ build.gradle
│  ├─ settings.gradle
│  └─ Dockerfile
├─ Poneglyph/          # Worker (C++20)
│  ├─ main.cpp         # Polls master, executes map/reduce via embedded Python calls
│  ├─ CMakeLists.txt
│  └─ Dockerfile
├─ client/             # Clover (Python)
│  ├─ submit_job.py    # Submits job, polls status, fetches result
│  ├─ map.py           # Example mapper (WordCount)
│  ├─ reduce.py        # Example reducer (WordCount)
│  └─ Dockerfile
└─ docker-compose.yml  # One master, N workers, client container
```

## 5) Quick start (with Docker)

```bash
# From the repo root:
docker compose up --build --scale worker=3 -d

# Follow master logs:
docker logs -f road-poneglyph

# Re-run the client (submits WordCount and prints the result):
docker compose run --rm client
```

> Default ports: Master exposes `:8080`.

## 6) API (v1 sketch)

* **POST** `/api/jobs` → submit a job package (Python scripts in Base64, split/reducers/input).
* **GET**  `/api/jobs/status?job_id=...` → job state + counters.
* **GET**  `/api/jobs/result?job_id=...` → final output (when `SUCCEEDED`).
* **POST** `/api/workers/register` → workers announce themselves.
* **GET**  `/api/tasks/next?workerId=...` → workers poll for MAP/REDUCE tasks.
* **POST** `/api/tasks/complete` → workers report MAP/REDUCE completion.

> The spec explicitly requires defining **Client ↔ Master** and **Master ↔ Workers** communications; this API covers the required flows.&#x20;

## 7) Example job (WordCount)

**Mapper (`map.py`)**: tokenize to lowercase words and emit `word\t1`.
**Reducer (`reduce.py`)**: sum counts per word and emit `word\tcount`.

The **client** encodes both scripts as Base64, sets `split_size` and `reducers`, and submits the job. This aligns with the GridMR “program package” requirements (map/reduce functions, partition params, input location, optional globals/deps).&#x20;

## 8) Why this matches the GridMR brief

* **Master-Workers** architecture, HTTP across Internet-exposed nodes, containerized services. &#x20;
* **Task planning**: split input, assign Map, collect intermediates, run Reduce, consolidate results. &#x20;
* **Program package** includes job id, `map()/reduce()`, partition parameters, and input location/content.&#x20;
* **Data modes** considered (transfer vs. API to distributed storage), with a simple transfer mode in v1 and a clear path to GridFS/S3 in v2. &#x20;
* **Tech choice** follows the spec suggestions (REST now; gRPC/Kafka/etc. as optional enhancements).&#x20;

## 9) Roadmap (next iterations)

* **Fault tolerance**: task timeouts, retries, worker heartbeats, re-queue.
* **Storage**: GridFS/S3 (e.g., MinIO) for intermediate and final outputs.
* **Scheduling**: capacity-aware & load-balanced placement (as the brief encourages).&#x20;
* **gRPC** for efficient binary exchange; **Kafka/RabbitMQ** for async shuffles or eventing.&#x20;
* **Security**: tokens per worker/job, auth on control plane.
* **More examples**: inverted index, PageRank, Monte Carlo.

> The assignment also asks for: a **technical report**, a **well-documented repo**, and a **demo video**—items this project structure is designed to support. &#x20;

## 10) Requirements

* **Master**: Java **17+** (Docker image uses JRE 17; local JDK 24 works fine).
* **Workers**: C++20 toolchain, `curl`, `python3` (all baked in the Docker image).
* **Client**: Python 3.10+.

> You can also run everything **fully containerized** with `docker compose` and avoid installing host toolchains.

## 11) A note on the lore 🌊

* The **Road-Poneglyph** *leads to the truth*: it knows where shards go and how to combine them—the central planner and consolidator.
* Each **Poneglyph** worker *holds a fragment* and processes it, forwarding the decipherable pieces.
* **Clover** is the scholar who can read Poneglyphs—our client orchestrating the story (job) and interpreting the final record.

## 12) Usage

```bash
# From the repo root:
docker compose up --build --scale worker=3 -d

# Follow master logs:
docker logs -f road-poneglyph

# Re-run the client (submits WordCount and prints result):
docker compose run --rm client
```

**References**

- Hadoop tutorial.
- Zaharia et al., "Resilient Distributed Datasets: A Fault-Tolerant Abstraction for In-Memory Cluster Computing", NSDI 2012.
- etc.
