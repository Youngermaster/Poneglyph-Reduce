cmake_minimum_required(VERSION 3.20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
project(Poneglyph LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(Poneglyph
        main.cpp
        model/http.hpp
        model/json.hpp
        model/worker.hpp
        core/worker.cpp
        telemetry/mqtt.hpp
        telemetry/mqtt.cpp)

target_include_directories(Poneglyph PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/model
        ${CMAKE_CURRENT_SOURCE_DIR}/core
        ${CMAKE_CURRENT_SOURCE_DIR}/telemetry
)

# Link Paho MQTT C++ and C (Debian/Ubuntu packages provide these)
find_library(PAHO_CPP_LIB paho-mqttpp3)
find_library(PAHO_C_LIB paho-mqtt3a)

if (NOT PAHO_CPP_LIB OR NOT PAHO_C_LIB)
    message(FATAL_ERROR "Paho MQTT libraries not found. Install libpaho-mqttpp3-dev and libpaho-mqtt-dev.")
endif ()

target_link_libraries(Poneglyph PRIVATE ${PAHO_CPP_LIB} ${PAHO_C_LIB})
