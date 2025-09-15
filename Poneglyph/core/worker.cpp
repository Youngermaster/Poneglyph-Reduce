#include "model/worker.hpp"
#include "model/http.hpp"
#include "model/json.hpp"
#include "telemetry/mqtt.hpp"

#include <chrono>
#include <iostream>
#include <sstream>
#include <thread>

Worker::Worker(std::string masterUrl,
               std::unique_ptr<telemetry::MqttClientManager> mqttClient)
    : master(std::move(masterUrl)), mqtt(std::move(mqttClient)) {
}

long long Worker::now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

void Worker::registerSelf() {
    std::string reg = http_post_json(master + "/api/workers/register",
                                     R"({"name":"ohara-scribe","capacity":1})");
    workerId = get_json_str(reg, "worker_id");
    std::cout << "Registered as " << workerId << std::endl;

    if (mqtt) {
        std::ostringstream j;
        j << "{\"workerId\":\"" << workerId << "\","
                << "\"name\":\"ohara-scribe\",\"capacity\":1,"
                << "\"ts\":" << now_ms() << "}";
        mqtt->publish_json("gridmr/worker/registered", j.str());
    }
}

void Worker::startHeartbeat() {
    if (!mqtt) return;
    std::thread([this] {
        while (true) {
            if (!workerId.empty()) {
                std::ostringstream j;
                j << "{\"ts\":" << now_ms() << "}";
                mqtt->publish_json("gridmr/worker/" + workerId + "/heartbeat", j.str());
            }
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    }).detach();
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
        if (c == '\\' || c == '\"') payload << '\\' << c;
        else if (c == '\n') payload << "\\n";
        else if (c == '\t') payload << "\\t";
        else payload << c;
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
        if (c == '\\' || c == '\"') payload << '\\' << c;
        else if (c == '\n') payload << "\\n";
        else if (c == '\t') payload << "\\t";
        else payload << c;
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
    std::cout << "Poneglyph Worker starting. Master=" << master << std::endl;
    registerSelf();
    startHeartbeat();

    while (true) {
        std::string task = http_get(master + "/api/tasks/next?workerId=" + workerId);
        if (task.empty()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(800));
            continue;
        }
        std::string type = get_json_str(task, "type");
        if (type == "MAP") handleMap(task);
        else if (type == "REDUCE") handleReduce(task);
        else std::this_thread::sleep_for(std::chrono::milliseconds(300));
    }
    // unreachable
    // return 0;
}
