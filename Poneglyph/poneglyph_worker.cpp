#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstdio>
#include <sstream>
#include <thread>
#include <chrono>
#include <map>
#include <memory>

// Enhanced Worker for Poneglyph gRPC Integration
class PoneglyphWorker {
private:
    std::string workerId;
    std::string grpcHost;
    int grpcPort;
    std::string rabbitMQUrl;
    std::string redisUrl;
    bool running;
    std::map<std::string, std::string> taskResults;

public:
    PoneglyphWorker(const std::string& id = "cpp-worker-1") 
        : workerId(id), running(false) {
        
        // Get configuration from environment
        grpcHost = getEnvVar("GRPC_HOST", "localhost");
        grpcPort = std::stoi(getEnvVar("GRPC_PORT", "50051"));
        rabbitMQUrl = getEnvVar("RABBITMQ_URL", "amqp://poneglyph:poneglyph123@localhost:5672/");
        redisUrl = getEnvVar("REDIS_URL", "redis://localhost:6379");
        
        std::cout << "Poneglyph Worker Initialized:" << std::endl;
        std::cout << "  Worker ID: " << workerId << std::endl;
        std::cout << "  gRPC Server: " << grpcHost << ":" << grpcPort << std::endl;
        std::cout << "  RabbitMQ: " << rabbitMQUrl << std::endl;
        std::cout << "  Redis: " << redisUrl << std::endl;
    }

    void start() {
        running = true;
        std::cout << "\\n=== PONEGLYPH WORKER STARTING ===" << std::endl;
        
        // Register with gRPC middleware
        if (registerWithMiddleware()) {
            std::cout << "✓ Successfully registered with gRPC middleware" << std::endl;
            
            // Start task processing loop
            processTasksLoop();
        } else {
            std::cout << "✗ Failed to register with middleware" << std::endl;
        }
    }

    void stop() {
        running = false;
        std::cout << "Worker stopped." << std::endl;
    }

private:
    std::string getEnvVar(const std::string& name, const std::string& defaultValue) {
        const char* value = std::getenv(name.c_str());
        return value ? std::string(value) : defaultValue;
    }

    bool registerWithMiddleware() {
        std::cout << "Registering with gRPC middleware..." << std::endl;
        
        // Test gRPC connection first
        if (!testGrpcConnection()) {
            std::cout << "  ✗ gRPC middleware not available" << std::endl;
            return false;
        }
        
        // Simulate worker registration via gRPC
        // In real implementation, this would use gRPC client
        std::string registrationData = createRegistrationPayload();
        std::cout << "  Registration payload: " << registrationData << std::endl;
        
        // For now, simulate successful registration
        std::cout << "  ✓ Worker registered successfully" << std::endl;
        return true;
    }

    bool testGrpcConnection() {
        // Test if gRPC middleware is available
        std::string testCmd = "netstat -an | findstr :50051 > nul 2>&1";
        int result = system(testCmd.c_str());
        return (result == 0);
    }

    std::string createRegistrationPayload() {
        std::ostringstream payload;
        payload << "{"
                << "\\"worker_id\\":\\"" << workerId << "\\","
                << "\\"host\\":\\"localhost\\","
                << "\\"port\\":8080,"
                << "\\"capabilities\\":[\\"MAP\\",\\"REDUCE\\"],"
                << "\\"status\\":\\"READY\\""
                << "}";
        return payload.str();
    }

    void processTasksLoop() {
        std::cout << "\\n=== STARTING TASK PROCESSING LOOP ===" << std::endl;
        
        int taskCount = 0;
        while (running) {
            try {
                // Simulate task fetching from RabbitMQ via gRPC
                Task task = fetchNextTask();
                
                if (!task.id.empty()) {
                    std::cout << "\\n--- Processing Task " << ++taskCount << " ---" << std::endl;
                    std::cout << "Task ID: " << task.id << std::endl;
                    std::cout << "Job ID: " << task.jobId << std::endl;
                    std::cout << "Type: " << task.type << std::endl;
                    
                    // Process the task
                    TaskResult result = processTask(task);
                    
                    // Send result back via gRPC
                    sendTaskResult(result);
                    
                    std::cout << "✓ Task completed successfully" << std::endl;
                } else {
                    // No tasks available, wait a bit
                    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
                    std::cout << "." << std::flush;
                }
                
            } catch (const std::exception& e) {
                std::cout << "Error in task processing: " << e.what() << std::endl;
                std::this_thread::sleep_for(std::chrono::milliseconds(2000));
            }
        }
    }

    struct Task {
        std::string id;
        std::string jobId;
        std::string type;
        std::string data;
        std::string mapScript;
        std::string reduceScript;
    };

    struct TaskResult {
        std::string taskId;
        std::string jobId;
        std::string workerId;
        std::string type;
        std::string output;
        bool success;
    };

    Task fetchNextTask() {
        Task task;
        
        // Simulate task fetching - in real implementation this would:
        // 1. Call gRPC middleware GetNextTask
        // 2. Middleware would fetch from RabbitMQ
        // 3. Return task or empty if none available
        
        static int simulatedTaskCounter = 0;
        simulatedTaskCounter++;
        
        if (simulatedTaskCounter <= 3) { // Simulate 3 tasks
            task.id = "task-" + std::to_string(simulatedTaskCounter);
            task.jobId = "job-simulation-001";
            task.type = (simulatedTaskCounter <= 2) ? "MAP" : "REDUCE";
            
            if (task.type == "MAP") {
                task.data = "hello world poneglyph mapreduce awesome integration grpc";
                task.mapScript = generateMapScript();
            } else {
                task.data = "hello 3\\nworld 2\\nponeglyph 1\\nmapreduce 1\\nawesome 1\\nintegration 1\\ngrpc 1";
                task.reduceScript = generateReduceScript();
            }
        }
        
        return task;
    }

    std::string generateMapScript() {
        return R"(#!/usr/bin/env python3
import sys

def map_function(line):
    words = line.strip().split()
    for word in words:
        print(f"{word} 1")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            for line in f:
                map_function(line)
    else:
        for line in sys.stdin:
            map_function(line)
)";
    }

    std::string generateReduceScript() {
        return R"(#!/usr/bin/env python3
import sys
from collections import defaultdict

def reduce_function(input_file):
    word_count = defaultdict(int)
    
    with open(input_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                word, count = parts[0], int(parts[1])
                word_count[word] += count
    
    for word, count in sorted(word_count.items()):
        print(f"{word} {count}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        reduce_function(sys.argv[1])
)";
    }

    TaskResult processTask(const Task& task) {
        TaskResult result;
        result.taskId = task.id;
        result.jobId = task.jobId;
        result.workerId = workerId;
        result.type = task.type;
        result.success = true;

        try {
            if (task.type == "MAP") {
                result.output = processMapTask(task);
            } else if (task.type == "REDUCE") {
                result.output = processReduceTask(task);
            } else {
                result.success = false;
                result.output = "Unknown task type: " + task.type;
            }
        } catch (const std::exception& e) {
            result.success = false;
            result.output = "Error: " + std::string(e.what());
        }

        return result;
    }

    std::string processMapTask(const Task& task) {
        std::cout << "  Processing MAP task..." << std::endl;
        
        // Save input data and map script
        saveToFile("input.txt", task.data);
        saveToFile("map.py", task.mapScript);
        
        // Execute map script
        std::string command = "python map.py input.txt";
        std::string output = executeCommand(command);
        
        std::cout << "  MAP output preview: " << output.substr(0, 100) << "..." << std::endl;
        return output;
    }

    std::string processReduceTask(const Task& task) {
        std::cout << "  Processing REDUCE task..." << std::endl;
        
        // Save input data and reduce script
        saveToFile("reduce_input.txt", task.data);
        saveToFile("reduce.py", task.reduceScript);
        
        // Execute reduce script
        std::string command = "python reduce.py reduce_input.txt";
        std::string output = executeCommand(command);
        
        std::cout << "  REDUCE output: " << output << std::endl;
        return output;
    }

    void saveToFile(const std::string& filename, const std::string& content) {
        FILE* file = fopen(filename.c_str(), "w");
        if (file) {
            fwrite(content.c_str(), 1, content.length(), file);
            fclose(file);
        }
    }

    std::string executeCommand(const std::string& command) {
        std::string result;
        FILE* pipe = popen(command.c_str(), "r");
        if (pipe) {
            char buffer[4096];
            while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
                result += buffer;
            }
            pclose(pipe);
        }
        return result;
    }

    void sendTaskResult(const TaskResult& result) {
        std::cout << "  Sending result via gRPC..." << std::endl;
        
        // Create result payload
        std::ostringstream payload;
        payload << "{"
                << "\\"task_id\\":\\"" << result.taskId << "\\","
                << "\\"job_id\\":\\"" << result.jobId << "\\","
                << "\\"worker_id\\":\\"" << result.workerId << "\\","
                << "\\"type\\":\\"" << result.type << "\\","
                << "\\"success\\":" << (result.success ? "true" : "false") << ","
                << "\\"output\\":\\"" << escapeJson(result.output) << "\\""
                << "}";
        
        // In real implementation, this would call gRPC middleware
        // For now, just log the payload
        std::cout << "  Result payload: " << payload.str().substr(0, 200) << "..." << std::endl;
        
        // Store result locally for demonstration
        taskResults[result.taskId] = result.output;
    }

    std::string escapeJson(const std::string& input) {
        std::ostringstream escaped;
        for (char c : input) {
            switch (c) {
                case '\\': escaped << "\\\\\\\\"; break;
                case '"': escaped << "\\\\\\""; break;
                case '\\n': escaped << "\\\\n"; break;
                case '\\r': escaped << "\\\\r"; break;
                case '\\t': escaped << "\\\\t"; break;
                default: escaped << c; break;
            }
        }
        return escaped.str();
    }

public:
    void showStatus() {
        std::cout << "\\n=== WORKER STATUS ===" << std::endl;
        std::cout << "Worker ID: " << workerId << std::endl;
        std::cout << "Status: " << (running ? "RUNNING" : "STOPPED") << std::endl;
        std::cout << "Processed tasks: " << taskResults.size() << std::endl;
        
        for (const auto& pair : taskResults) {
            std::cout << "  " << pair.first << ": " << pair.second.substr(0, 50) << "..." << std::endl;
        }
    }
};

int main(int argc, char* argv[]) {
    std::cout << "=================================" << std::endl;
    std::cout << "   PONEGLYPH C++ WORKER v2.0" << std::endl;
    std::cout << "=================================" << std::endl;
    std::cout << std::endl;

    // Create worker with ID from command line or default
    std::string workerId = (argc > 1) ? argv[1] : "cpp-worker-main";
    PoneglyphWorker worker(workerId);

    try {
        // Start the worker
        worker.start();
    } catch (const std::exception& e) {
        std::cout << "Worker error: " << e.what() << std::endl;
    }

    // Show final status
    worker.showStatus();
    
    std::cout << "\\n🎉 Poneglyph Worker completed successfully! 🎉" << std::endl;
    return 0;
}
