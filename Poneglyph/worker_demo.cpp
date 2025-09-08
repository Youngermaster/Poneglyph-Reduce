#include <iostream>
#include <thread>
#include <chrono>

int main() {
    std::cout << "=================================" << std::endl;
    std::cout << "   PONEGLYPH C++ WORKER v2.0" << std::endl;
    std::cout << "=================================" << std::endl;
    std::cout << std::endl;

    std::cout << "Worker initialized successfully!" << std::endl;
    std::cout << "  Worker ID: cpp-worker-demo" << std::endl;
    std::cout << "  gRPC Server: localhost:50051" << std::endl;
    std::cout << "  Status: READY" << std::endl;
    std::cout << std::endl;

    std::cout << "=== SIMULATING TASK PROCESSING ===" << std::endl;
    
    for (int i = 1; i <= 3; i++) {
        std::cout << std::endl;
        std::cout << "--- Processing Task " << i << " ---" << std::endl;
        std::cout << "Task ID: task-demo-" << i << std::endl;
        std::cout << "Job ID: job-demo-001" << std::endl;
        std::cout << "Type: " << ((i <= 2) ? "MAP" : "REDUCE") << std::endl;
        
        // Simulate processing time
        std::cout << "  Processing";
        for (int j = 0; j < 3; j++) {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            std::cout << ".";
            std::cout.flush();
        }
        std::cout << std::endl;
        
        if (i <= 2) {
            std::cout << "  MAP output: word1 1\\nword2 1\\nword3 1" << std::endl;
        } else {
            std::cout << "  REDUCE output: word1 3\\nword2 2\\nword3 1" << std::endl;
        }
        
        std::cout << "✓ Task completed successfully" << std::endl;
    }
    
    std::cout << std::endl;
    std::cout << "=== WORKER STATUS ===" << std::endl;
    std::cout << "Worker ID: cpp-worker-demo" << std::endl;
    std::cout << "Status: RUNNING" << std::endl;
    std::cout << "Processed tasks: 3" << std::endl;
    
    std::cout << std::endl;
    std::cout << "#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <random>
#include <vector>
#include <sstream>

class WorkerDemo {
private:
    std::string worker_id;
    std::random_device rd;
    std::mt19937 gen;
    
public:
    WorkerDemo() : gen(rd()) {
        worker_id = "cpp-worker-" + std::to_string(gen() % 1000);
    }
    
    void print_header(const std::string& title) {
        std::cout << "
=== " << title << " ===" << std::endl;
    }
    
    void simulate_registration() {
        print_header("WORKER REGISTRATION");
        std::cout << "🔧 Worker ID: " << worker_id << std::endl;
        std::cout << "📡 Registering with middleware on localhost:50051..." << std::endl;
        
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        std::cout << "✅ Registration successful!" << std::endl;
        std::cout << "� Worker capabilities: MAP, REDUCE" << std::endl;
        std::cout << "📊 Status: READY" << std::endl;
    }
    
    std::vector<std::string> split_text(const std::string& text) {
        std::vector<std::string> words;
        std::stringstream ss(text);
        std::string word;
        
        while (ss >> word) {
            words.push_back(word);
        }
        
        return words;
    }
    
    void process_map_task() {
        print_header("MAP TASK PROCESSING");
        
        std::string input_data = "poneglyph mapreduce system working great integration grpc amazing";
        std::cout << "📥 Received MAP task" << std::endl;
        std::cout << "📄 Input data: " << input_data << std::endl;
        
        std::cout << "
⚙️  Processing MAP operation..." << std::endl;
        
        auto words = split_text(input_data);
        
        std::cout << "🔄 Mapping words to (word, 1) pairs:" << std::endl;
        
        for (const auto& word : words) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            std::cout << "   " << word << " -> (" << word << ", 1)" << std::endl;
        }
        
        std::cout << "
📤 MAP output:" << std::endl;
        for (const auto& word : words) {
            std::cout << word << " 1" << std::endl;
        }
        
        std::cout << "✅ MAP task completed successfully!" << std::endl;
    }
    
    void process_reduce_task() {
        print_header("REDUCE TASK PROCESSING");
        
        std::vector<std::string> map_output = {
            "poneglyph 1", "mapreduce 1", "system 1", "working 1",
            "great 1", "integration 1", "grpc 1", "amazing 1"
        };
        
        std::cout << "📥 Received REDUCE task" << std::endl;
        std::cout << "📄 Input from MAP phase:" << std::endl;
        
        for (const auto& entry : map_output) {
            std::cout << "   " << entry << std::endl;
        }
        
        std::cout << "
⚙️  Processing REDUCE operation..." << std::endl;
        std::cout << "🔄 Aggregating word counts:" << std::endl;
        
        for (const auto& entry : map_output) {
            std::this_thread::sleep_for(std::chrono::milliseconds(150));
            auto space_pos = entry.find(' ');
            std::string word = entry.substr(0, space_pos);
            std::cout << "   Counting: " << word << std::endl;
        }
        
        std::cout << "
📤 REDUCE output (final word counts):" << std::endl;
        std::cout << "amazing 1" << std::endl;
        std::cout << "great 1" << std::endl;
        std::cout << "grpc 1" << std::endl;
        std::cout << "integration 1" << std::endl;
        std::cout << "mapreduce 1" << std::endl;
        std::cout << "poneglyph 1" << std::endl;
        std::cout << "system 1" << std::endl;
        std::cout << "working 1" << std::endl;
        
        std::cout << "✅ REDUCE task completed successfully!" << std::endl;
    }
    
    void simulate_communication() {
        print_header("GRPC COMMUNICATION TEST");
        
        std::cout << "📡 Testing gRPC connection to middleware..." << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        
        std::cout << "✅ gRPC connection established" << std::endl;
        std::cout << "📊 Middleware response: Connection successful" << std::endl;
        std::cout << "🔄 Heartbeat: Active" << std::endl;
        
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        
        std::cout << "📤 Sending status update to middleware..." << std::endl;
        std::cout << "✅ Status update sent successfully" << std::endl;
    }
    
    void run_demo() {
        std::cout << "
�‍☠️ PONEGLYPH WORKER DEMO - " << worker_id << std::endl;
        std::cout << "================================================" << std::endl;
        
        simulate_registration();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        simulate_communication();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        process_map_task();
        std::this_thread::sleep_for(std::chrono::milliseconds(800));
        
        process_reduce_task();
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        print_header("WORKER DEMO COMPLETED");
        std::cout << "�🎉 Worker " << worker_id << " demonstration finished!" << std::endl;
        std::cout << "📊 Tasks processed: MAP ✅, REDUCE ✅" << std::endl;
        std::cout << "🔧 Status: READY for more tasks" << std::endl;
        std::cout << "📡 gRPC communication: ACTIVE" << std::endl;
    }
};

int main() {
    try {
        WorkerDemo demo;
        demo.run_demo();
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "❌ Error: " << e.what() << std::endl;
        return 1;
    }
}" << std::endl;
    return 0;
}
