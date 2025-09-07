#pragma once
#include <cctype>
#include <string>

/**
 * Extract a JSON string value by key from a flat object (very small helper).
 * Properly unescapes \n, \t, \r, \\, \", and ignores \uXXXX sequences.
 * Not a general JSON parser; good enough for our controlled payloads.
 */
inline std::string get_json_str(const std::string &j, const std::string &key) {
    std::string pat = "\"" + key + "\":";
    size_t p = j.find(pat);
    if (p == std::string::npos) return "";
    p += pat.size();
    while (p < j.size() && j[p] == ' ') ++p;

    if (p < j.size() && j[p] == '"') {
        ++p;
        std::string val;
        while (p < j.size()) {
            char c = j[p++];
            if (c == '\\') {
                if (p >= j.size()) break;
                char e = j[p++];
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
                        for (int k = 0; k < 4 && p < j.size(); ++k)
                            if (isxdigit(static_cast<unsigned char>(j[p]))) ++p;
                        break;
                    default: val.push_back(e);
                        break;
                }
            } else if (c == '"') {
                break;
            } else {
                val.push_back(c);
            }
        }
        return val;
    }

    // number
    std::string val;
    while (p < j.size() && (std::isdigit(static_cast<unsigned char>(j[p])) || j[p] == '-' || j[p] == '.'))
        val.push_back(j[p++]);
    return val;
}
