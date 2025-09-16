#pragma once
#include <memory>
#include <string>
#include <iostream>
#include <grpcpp/grpcpp.h>
#include "gridmr.grpc.pb.h"

class MasterGrpcClient {
public:
    explicit MasterGrpcClient(const std::string &addr)
        : channel_(grpc::CreateChannel(addr, grpc::InsecureChannelCredentials())),
          stub_(gridmr::Master::NewStub(channel_)) {
    }

    bool RegisterWorker(const std::string &name, int capacity, std::string &out_worker_id, int *poll_ms = nullptr) {
        gridmr::WorkerRegisterRequest req;
        req.set_name(name);
        req.set_capacity(capacity);
        gridmr::WorkerRegisterResponse resp;
        grpc::ClientContext ctx;
        auto status = stub_->Register(&ctx, req, &resp);
        if (!status.ok()) {
            std::cerr << "[gRPC] Register failed: " << status.error_code() << " - " << status.error_message() << std::endl;
            return false;
        }
        out_worker_id = resp.worker_id();
        if (poll_ms) *poll_ms = resp.poll_interval_ms();
        return true;
    }

    bool NextTask(const std::string &worker_id, gridmr::TaskAssignment &out) {
        gridmr::NextTaskRequest req;
        req.set_worker_id(worker_id);
        grpc::ClientContext ctx;
        auto status = stub_->NextTask(&ctx, req, &out);
        return status.ok();
    }

    bool CompleteMap(const std::string &worker_id,
                     const std::string &task_id,
                     const std::string &job_id,
                     const std::string &kv_lines) {
        gridmr::CompleteMapRequest req;
        req.set_worker_id(worker_id);
        req.set_task_id(task_id);
        req.set_job_id(job_id);
        req.set_kv_lines(kv_lines);
        gridmr::Ack ack;
        grpc::ClientContext ctx;
        auto status = stub_->CompleteMap(&ctx, req, &ack);
        return status.ok() && ack.ok();
    }

    bool CompleteReduce(const std::string &worker_id,
                        const std::string &task_id,
                        const std::string &job_id,
                        const std::string &output) {
        gridmr::CompleteReduceRequest req;
        req.set_worker_id(worker_id);
        req.set_task_id(task_id);
        req.set_job_id(job_id);
        req.set_output(output);
        gridmr::Ack ack;
        grpc::ClientContext ctx;
        auto status = stub_->CompleteReduce(&ctx, req, &ack);
        return status.ok() && ack.ok();
    }

private:
    std::shared_ptr<grpc::Channel> channel_;
    std::unique_ptr<gridmr::Master::Stub> stub_;
};
