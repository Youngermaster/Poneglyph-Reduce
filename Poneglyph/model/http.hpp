#pragma once
#include <cstdio>
#include <string>

inline std::string sh(const std::string &cmd) {
    std::string full = cmd + " 2>/dev/null";
    FILE *pipe = popen(full.c_str(), "r");
    if (!pipe) return "";
    char buf[4096];
    std::string out;
    while (fgets(buf, sizeof(buf), pipe) != nullptr) out += buf;
    pclose(pipe);
    return out;
}

inline std::string http_get(const std::string &url) {
    return sh("curl -s " + url);
}

inline std::string http_post_json(const std::string &url, const std::string &json) {
    return sh("curl -s -X POST -H 'Content-Type: application/json' --data '" + json + "' " + url);
}

inline void save_file(const std::string &path, const std::string &data) {
    if (FILE *f = fopen(path.c_str(), "wb")) {
        fwrite(data.data(), 1, data.size(), f);
        fclose(f);
    }
}
