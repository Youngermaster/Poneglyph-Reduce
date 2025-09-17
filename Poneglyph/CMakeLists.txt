cmake_minimum_required(VERSION 3.20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
project(Poneglyph LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- gRPC / Protobuf ----
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

# Paths
set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/proto)
set(PROTO_FILE ${PROTO_DIR}/gridmr.proto)
set(GEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
file(MAKE_DIRECTORY ${GEN_DIR})

# Generate protobuf sources
add_custom_command(
        OUTPUT ${GEN_DIR}/gridmr.pb.cc ${GEN_DIR}/gridmr.pb.h
        COMMAND protobuf::protoc
        ARGS --cpp_out ${GEN_DIR} -I ${PROTO_DIR} ${PROTO_FILE}
        DEPENDS ${PROTO_FILE}
)

# Generate gRPC sources
add_custom_command(
        OUTPUT ${GEN_DIR}/gridmr.grpc.pb.cc ${GEN_DIR}/gridmr.grpc.pb.h
        COMMAND protobuf::protoc
        ARGS --grpc_out ${GEN_DIR} --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin> -I ${PROTO_DIR} ${PROTO_FILE}
        DEPENDS ${PROTO_FILE}
)

add_library(gridmr_proto
        ${GEN_DIR}/gridmr.pb.cc
        ${GEN_DIR}/gridmr.grpc.pb.cc
)

target_include_directories(gridmr_proto PUBLIC ${GEN_DIR})
target_link_libraries(gridmr_proto PUBLIC protobuf::libprotobuf gRPC::grpc++)

# ---- MQTT ----
find_library(PAHO_CPP_LIB paho-mqttpp3 REQUIRED)
find_library(PAHO_C_LIB paho-mqtt3a REQUIRED)

# ---- Worker binary ----
add_executable(Poneglyph
        main.cpp
        model/http.hpp
        model/json.hpp
        model/worker.hpp
        core/worker.cpp
        telemetry/mqtt.hpp
        telemetry/mqtt.cpp
        rpc/grpc_client.hpp
)

target_include_directories(Poneglyph PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/model
        ${CMAKE_CURRENT_SOURCE_DIR}/core
        ${CMAKE_CURRENT_SOURCE_DIR}/telemetry
        ${CMAKE_CURRENT_SOURCE_DIR}/rpc
)

# Verify MQTT libraries are found
if (NOT PAHO_CPP_LIB OR NOT PAHO_C_LIB)
    message(FATAL_ERROR "Paho MQTT libraries not found. Install libpaho-mqttpp-dev and libpaho-mqtt-dev.")
endif ()

target_link_libraries(Poneglyph
        PRIVATE
        gridmr_proto
        gRPC::grpc++
        protobuf::libprotobuf
        ${PAHO_CPP_LIB}
        ${PAHO_C_LIB}
)
