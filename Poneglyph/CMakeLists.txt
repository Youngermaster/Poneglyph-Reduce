cmake_minimum_required(VERSION 3.20)
project(Poneglyph LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Original worker (HTTP-based)
add_executable(Poneglyph main.cpp)

# Enhanced worker (gRPC integration)
add_executable(PoneglyphWorker poneglyph_worker.cpp)
