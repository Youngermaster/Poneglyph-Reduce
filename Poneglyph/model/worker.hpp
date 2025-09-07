#pragma once
#include <string>

class Worker {
public:
    explicit Worker(std::string masterUrl);

    int run(); // main loop

private:
    std::string master;
    std::string workerId;

    void registerSelf();

    void handleMap(const std::string &taskJson);

    void handleReduce(const std::string &taskJson);
};
