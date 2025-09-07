#include "model/worker.hpp"
#include <cstdlib>
#include <string>

int main() {
    std::string master = std::getenv("PONEGLYPH_MASTER_URL")
                             ? std::getenv("PONEGLYPH_MASTER_URL")
                             : "http://localhost:8080";
    Worker w(master);
    return w.run();
}
