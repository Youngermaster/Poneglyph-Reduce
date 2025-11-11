#include "model/worker.hpp"

#include <chrono>
#include <iostream>
#include <mutex>
#include <sstream>
#include <thread>

#include "gridmr.grpc.pb.h"
#include "model/http.hpp"
#include "model/json.hpp"
#include "rpc/grpc_client.hpp"
#include "telemetry/mqtt.hpp"

Worker::Worker(std::string masterUrl,
               std::unique_ptr<telemetry::MqttClientManager> mqttClient,
               std::unique_ptr<MasterGrpcClient> grpcClient)
    : master(std::move(masterUrl)), mqtt(std::move(mqttClient)), grpc(std::move(grpcClient)) {
}

long long Worker::now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

void Worker::registerSelf() {
    auto [cpuUsage, memUsage] = getSystemMetrics();

    // Generate unique worker name using timestamp
    auto now = std::chrono::high_resolution_clock::now();
    auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
    std::string uniqueWorkerName = "poneglyph-worker-" + std::to_string(timestamp);

    // Prefer gRPC if available
    if (grpc) {
        std::string wid;
        int poll_ms = 1000;
        bool ok = grpc->RegisterWorker(uniqueWorkerName, /*capacity*/ 2, wid, &poll_ms);
        if (ok && !wid.empty()) {
            workerId = wid;
            std::cout << "[gRPC] Registered as " << workerId << " (poll=" << poll_ms << "ms)\n";
        } else {
            std::cerr << "[gRPC] Register failed, falling back to HTTP.\n";
        }
    }

    if (workerId.empty()) {
        // HTTP fallback
        std::ostringstream registrationPayload;
        registrationPayload << "{"
                << "\"name\":\"" << uniqueWorkerName << "\","
                << "\"capacity\":2," // Capacidad de tareas concurrentes
                << "\"cpu_usage\":" << cpuUsage << ","
                << "\"memory_usage\":" << memUsage
                << "}";
        std::string reg = http_post_json(master + "/api/workers/register", registrationPayload.str());
        workerId = get_json_str(reg, "worker_id");
        std::cout << "[HTTP] Registered as " << workerId << std::endl;
    }

    if (mqtt) {
        std::ostringstream j;
        j << "{\"workerId\":\"" << workerId << "\","
                << "\"name\":\"" << uniqueWorkerName << "\",\"capacity\":2,"
                << "\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/registered", j.str());
    }
}

void Worker::startHeartbeat() {
    std::thread([this] {
        while (true) {
            if (!workerId.empty()) {
                // Obtener métricas básicas del sistema
                auto [cpuUsage, memUsage] = getSystemMetrics();

                // Enviar heartbeat al Master via HTTP
                std::ostringstream heartbeatJson;
                heartbeatJson << "{\"worker_id\":\"" << workerId << "\","
                        << "\"cpu_usage\":" << cpuUsage << ","
                        << "\"memory_usage\":" << memUsage << ","
                        << "\"ts\":" << now_ms() << "}";

                try {
                    http_post_json(master + "/api/workers/heartbeat", heartbeatJson.str());
                } catch (const std::exception &e) {
                    std::cerr << "Heartbeat failed: " << e.what() << std::endl;
                }

                // También publicar via MQTT para el dashboard
                if (mqtt) {
                    mqtt->publish_json("gridmr/worker/" + workerId + "/heartbeat", heartbeatJson.str());
                }
            }
            std::this_thread::sleep_for(std::chrono::seconds(10)); // Cada 10 segundos
        }
    }).detach();
}

std::pair<double, double> Worker::getSystemMetrics() {
    // Implementación básica de métricas del sistema
    // En un sistema real, esto leería /proc/stat, /proc/meminfo, etc.

    // Initialize random seed if not done yet (thread-safe)
    static std::once_flag flag;
    std::call_once(flag, []() {
        auto seed = std::chrono::high_resolution_clock::now().time_since_epoch().count();
        std::srand(static_cast<unsigned int>(seed));
    });

    // Add small random variation based on worker instance
    auto now = std::chrono::steady_clock::now().time_since_epoch().count();
    double baseVariation = (now % 1000) / 1000.0; // 0.0-0.999

    double cpuUsage = 0.1 + (rand() % 30) / 100.0 + baseVariation * 0.05; // 10-45% CPU
    double memUsage = 0.2 + (rand() % 40) / 100.0 + baseVariation * 0.05; // 20-65% memoria

    return {cpuUsage, memUsage};
}

void Worker::handleMap(const std::string &taskJson) {
    std::string taskId = get_json_str(taskJson, "task_id");
    std::string jobId = get_json_str(taskJson, "job_id");
    std::string chunk = get_json_str(taskJson, "input_chunk");
    std::string mapUrl = get_json_str(taskJson, "map_url");

    // fetch scripts & input
    save_file("map.py", http_get(master + mapUrl));
    save_file("input.txt", chunk);

    // run mapper
    sh("python3 map.py input.txt > map.out");
    std::string kv = sh("cat map.out");

    if (kv.empty()) {
        std::cerr << "[WARN] Mapper produced 0 lines for " << taskId << std::endl;
    }

    // escape for JSON
    std::ostringstream payload;
    payload << "{"
            << "\"worker_id\":\"" << workerId << "\","
            << "\"task_id\":\"" << taskId << "\","
            << "\"job_id\":\"" << jobId << "\","
            << "\"type\":\"MAP\","
            << "\"kv_lines\":\"";
    for (char c: kv) {
        if (c == '\\' || c == '\"')
            payload << '\\' << c;
        else if (c == '\n')
            payload << "\\n";
        else if (c == '\t')
            payload << "\\t";
        else
            payload << c;
    }
    payload << "\"}";
    http_post_json(master + "/api/tasks/complete", payload.str());
    std::cout << "Completed MAP " << taskId << std::endl;

    if (mqtt) {
        std::ostringstream j;
        j << "{\"taskId\":\"" << taskId << "\",\"jobId\":\"" << jobId
                << "\",\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/" + workerId + "/map/completed", j.str());
    }
}

void Worker::handleReduce(const std::string &taskJson) {
    std::string taskId = get_json_str(taskJson, "task_id");
    std::string jobId = get_json_str(taskJson, "job_id");
    std::string reduceUrl = get_json_str(taskJson, "reduce_url");
    std::string kvLines = get_json_str(taskJson, "kv_lines");

    save_file("reduce.py", http_get(master + reduceUrl));
    save_file("reduce_in.txt", kvLines);

    sh("python3 reduce.py reduce_in.txt > reduce.out");
    std::string out = sh("cat reduce.out");

    if (out.empty()) {
        std::cerr << "[WARN] Reducer produced 0 lines for " << taskId << std::endl;
    }

    std::ostringstream payload;
    payload << "{"
            << "\"worker_id\":\"" << workerId << "\","
            << "\"task_id\":\"" << taskId << "\","
            << "\"job_id\":\"" << jobId << "\","
            << "\"type\":\"REDUCE\","
            << "\"output\":\"";
    for (char c: out) {
        if (c == '\\' || c == '\"')
            payload << '\\' << c;
        else if (c == '\n')
            payload << "\\n";
        else if (c == '\t')
            payload << "\\t";
        else
            payload << c;
    }
    payload << "\"}";
    http_post_json(master + "/api/tasks/complete", payload.str());
    std::cout << "Completed REDUCE " << taskId << std::endl;

    if (mqtt) {
        std::ostringstream j;
        j << "{\"taskId\":\"" << taskId << "\",\"jobId\":\"" << jobId
                << "\",\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/" + workerId + "/reduce/completed", j.str());
    }
}

int Worker::run() {
    std::cout << "Poneglyph Worker starting. Master(HTTP)=" << master
            << (grpc ? "  [gRPC enabled]" : "  [gRPC disabled]") << std::endl;

    registerSelf();
    startHeartbeat();

    while (true) {
        if (grpc) {
            gridmr::TaskAssignment ta;
            if (!grpc->NextTask(workerId, ta)) {
                std::cout << "[Worker " << workerId << "] gRPC NextTask failed" << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(800));
                continue;
            }
            if (!ta.has_task()) {
                // std::cout << "[Worker " << workerId << "] No tasks available" << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(800));
                continue;
            }
            if (ta.has_map()) {
                std::cout << "[Worker " << workerId << "] Received MAP task: " << ta.map().task_id() << std::endl;
                handleMapGrpc(ta.map());
            } else if (ta.has_reduce()) {
                std::cout << "[Worker " << workerId << "] Received REDUCE task: " << ta.reduce().task_id() << std::endl;
                handleReduceGrpc(ta.reduce());
            } else {
                std::cout << "[Worker " << workerId << "] Unknown task type" << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(300));
            }
            continue;
        }

        // HTTP fallback (existing behavior)
        std::string task = http_get(master + "/api/tasks/next?workerId=" + workerId);
        if (task.empty()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(800));
            continue;
        }
        std::string type = get_json_str(task, "type");
        if (type == "MAP")
            handleMap(task);
        else if (type == "REDUCE")
            handleReduce(task);
        else
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
    }
}

void Worker::handleMapGrpc(const gridmr::MapTask &mt) {
    // Map script: prefer embedded; else fetch via HTTP fallback URL
    if (!mt.map_script().empty()) {
        std::string s(mt.map_script().begin(), mt.map_script().end());
        save_file("map.py", s);
    } else {
        save_file("map.py", http_get(master + mt.map_url()));
    }
    // input
    save_file("input.txt", mt.input_chunk());

    // run
    sh("python3 map.py input.txt > map.out");
    std::string kv = sh("cat map.out");
    if (kv.empty()) std::cerr << "[WARN] Mapper produced 0 lines for " << mt.task_id() << std::endl;

    if (grpc) {
        if (!grpc->CompleteMap(workerId, mt.task_id(), mt.job_id(), kv)) {
            std::cerr << "[gRPC] CompleteMap failed\n";
        }
    } else {
        // Shouldn't happen, but keep symmetry
        std::ostringstream payload;
        payload << "{\"worker_id\":\"" << workerId << "\","
                << "\"task_id\":\"" << mt.task_id() << "\","
                << "\"job_id\":\"" << mt.job_id() << "\","
                << "\"type\":\"MAP\","
                << "\"kv_lines\":\"";
        for (char c: kv) {
            if (c == '\\' || c == '\"')
                payload << '\\' << c;
            else if (c == '\n')
                payload << "\\n";
            else if (c == '\t')
                payload << "\\t";
            else
                payload << c;
        }
        payload << "\"}";
        http_post_json(master + "/api/tasks/complete", payload.str());
    }

    if (mqtt) {
        std::ostringstream j;
        j << "{\"taskId\":\"" << mt.task_id() << "\",\"jobId\":\"" << mt.job_id()
                << "\",\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/" + workerId + "/map/completed", j.str());
    }
}

void Worker::handleReduceGrpc(const gridmr::ReduceTask &rt) {
    if (!rt.reduce_script().empty()) {
        std::string s(rt.reduce_script().begin(), rt.reduce_script().end());
        save_file("reduce.py", s);
    } else {
        save_file("reduce.py", http_get(master + rt.reduce_url()));
    }
    save_file("reduce_in.txt", rt.kv_lines());

    sh("python3 reduce.py reduce_in.txt > reduce.out");
    std::string out = sh("cat reduce.out");
    if (out.empty()) std::cerr << "[WARN] Reducer produced 0 lines for " << rt.task_id() << std::endl;

    if (grpc) {
        if (!grpc->CompleteReduce(workerId, rt.task_id(), rt.job_id(), out)) {
            std::cerr << "[gRPC] CompleteReduce failed\n";
        }
    } else {
        std::ostringstream payload;
        payload << "{\"worker_id\":\"" << workerId << "\","
                << "\"task_id\":\"" << rt.task_id() << "\","
                << "\"job_id\":\"" << rt.job_id() << "\","
                << "\"type\":\"REDUCE\","
                << "\"output\":\"";
        for (char c: out) {
            if (c == '\\' || c == '\"')
                payload << '\\' << c;
            else if (c == '\n')
                payload << "\\n";
            else if (c == '\t')
                payload << "\\t";
            else
                payload << c;
        }
        payload << "\"}";
        http_post_json(master + "/api/tasks/complete", payload.str());
    }

    if (mqtt) {
        std::ostringstream j;
        j << "{\"taskId\":\"" << rt.task_id() << "\",\"jobId\":\"" << rt.job_id()
                << "\",\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/" + workerId + "/reduce/completed", j.str());
    }
}
