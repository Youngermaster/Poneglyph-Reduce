#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

// Pequeña utilidad para ejecutar comandos del SO y capturar salida (requiere 'curl' y 'python3' instalados)
std::string run(const std::string &cmd) {
    std::string full = cmd + " 2>/dev/null";
    FILE *pipe = popen(full.c_str(), "r");
    if (!pipe) return "";
    char buffer[4096];
    std::string result;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) result += buffer;
    pclose(pipe);
    return result;
}

std::string http_post_json(const std::string &url, const std::string &json) {
    std::string cmd = "curl -s -X POST -H 'Content-Type: application/json' --data '" + json + "' " + url;
    return run(cmd);
}

std::string http_get(const std::string &url) {
    std::string cmd = "curl -s " + url;
    return run(cmd);
}

void save_file(const std::string &path, const std::string &data) {
    FILE *f = fopen(path.c_str(), "wb");
    if (!f) return;
    fwrite(data.data(), 1, data.size(), f);
    fclose(f);
}

// Naive JSON getters (busca "campo":"valor" en respuestas conocidas v1)
std::string get_json_str(const std::string &j, const std::string &key) {
    std::string pat = "\"" + key + "\":";
    size_t p = j.find(pat);
    if (p == std::string::npos) return "";
    p += pat.size();
    while (p < j.size() && (j[p] == ' ')) p++;

    // String
    if (p < j.size() && j[p] == '\"') {
        p++;
        std::string val;
        while (p < j.size()) {
            char c = j[p++];
            if (c == '\\') {
                if (p >= j.size()) break;
                char e = j[p++]; // escape code
                switch (e) {
                    case 'n': val.push_back('\n');
                        break;
                    case 't': val.push_back('\t');
                        break;
                    case 'r': val.push_back('\r');
                        break;
                    case 'b': val.push_back('\b');
                        break;
                    case 'f': val.push_back('\f');
                        break;
                    case '\\': val.push_back('\\');
                        break;
                    case '\"': val.push_back('\"');
                        break;
                    case 'u':
                        // ignora \uXXXX (no lo necesitamos aquí)
                        // salta hasta 4 hex si están
                        for (int k = 0; k < 4 && p < j.size(); ++k) {
                            if (!isxdigit((unsigned char) j[p])) break;
                            ++p;
                        }
                        break;
                    default:
                        // escape desconocido: conserva el char literal
                        val.push_back(e);
                        break;
                }
            } else if (c == '\"') {
                break; // fin de string
            } else {
                val.push_back(c);
            }
        }
        return val;
    }

    // Número simple
    std::string val;
    while (p < j.size() && (isdigit((unsigned char) j[p]) || j[p] == '-' || j[p] == '.')) {
        val.push_back(j[p++]);
    }
    return val;
}


int main() {
    std::string master = std::getenv("PONEGLYPH_MASTER_URL")
                             ? std::getenv("PONEGLYPH_MASTER_URL")
                             : "http://localhost:8080";
    std::cout << "Poneglyph Worker starting. Master=" << master << std::endl;

    // Register
    std::string regResp = http_post_json(master + "/api/workers/register", R"({"name":"ohara-scribe","capacity":1})");
    std::string workerId = get_json_str(regResp, "worker_id");
    std::cout << "Registered as " << workerId << std::endl;

    while (true) {
        std::string task = http_get(master + "/api/tasks/next?workerId=" + workerId);
        if (task.empty()) {
            // 204
            std::this_thread::sleep_for(std::chrono::milliseconds(800));
            continue;
        }
        std::string type = get_json_str(task, "type");
        std::string taskId = get_json_str(task, "task_id");
        std::string jobId = get_json_str(task, "job_id");

        if (type == "MAP") {
            std::string inputChunk = get_json_str(task, "input_chunk");
            std::string mapUrl = get_json_str(task, "map_url");
            // Descargar map.py
            std::string mapPy = http_get(master + mapUrl);
            save_file("map.py", mapPy);
            save_file("input.txt", inputChunk);

            // Ejecutar: python3 map.py input.txt > map.out
            run("python3 map.py input.txt > map.out");
            // Leer salida
            // ... dentro del bloque MAP, antes de enviar /api/tasks/complete
            // Leer salida
            std::string kv = run("cat map.out");

            // Aviso si el mapper no produjo nada
            if (kv.empty()) {
                std::cerr << "[WARN] Mapper produced 0 lines for task " << taskId << std::endl;
            }

            std::ostringstream payload;
            payload << "{"
                    << "\"worker_id\":\"" << workerId << "\","
                    << "\"task_id\":\"" << taskId << "\","
                    << "\"job_id\":\"" << jobId << "\","
                    << "\"type\":\"MAP\","
                    << "\"kv_lines\":\"";
            // escapar comillas, backslashes, NEWLINE y TAB
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
        } else if (type == "REDUCE") {
            std::string reduceUrl = get_json_str(task, "reduce_url");
            std::string kvLines = get_json_str(task, "kv_lines");
            // Guardar reduce input y script
            std::string rPy = http_get(master + reduceUrl);
            save_file("reduce.py", rPy);
            save_file("reduce_in.txt", kvLines);
            // Ejecutar reduce
            run("python3 reduce.py reduce_in.txt > reduce.out");
            // ... después de run("cat reduce.out");
            std::string out = run("cat reduce.out");

            // Aviso si el reducer no produjo nada
            if (out.empty()) {
                std::cerr << "[WARN] Reducer produced 0 lines for task " << taskId << std::endl;
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
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
    }
    return 0;
}
