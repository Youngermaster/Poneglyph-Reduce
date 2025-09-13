import os
import time
from typing import Dict, Optional, Any

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


class StateStore:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self._r = None
        if self.redis_url and redis:
            try:
                self._r = redis.Redis.from_url(self.redis_url, decode_responses=True)
                self._r.ping()
                print(f"StateStore: using Redis at {self.redis_url}")
            except Exception as e:
                print(f"StateStore: Redis unavailable ({e}), falling back to memory")
                self._r = None
        else:
            print("StateStore: using in-memory store")
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {}

    # Worker operations
    def upsert_worker(self, worker_id: str, info: Dict[str, Any]):
        now = int(time.time() * 1000)
        info = dict(info)
        info["last_heartbeat"] = now
        if self._r:
            self._r.hset(f"worker:{worker_id}", mapping={k: str(v) for k, v in info.items()})
        else:
            self._workers[worker_id] = info

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        if self._r:
            data = self._r.hgetall(f"worker:{worker_id}")
            return data or None
        return self._workers.get(worker_id)

    def list_workers(self):
        if self._r:
            # Simplified; in production, keep an index of worker IDs
            return []
        return list(self._workers.values())

    def get_all_workers(self) -> Dict[str, Dict[str, Any]]:
        """Get all workers as a dictionary {worker_id: worker_data}"""
        if self._r:
            # In production, you'd implement proper pattern matching
            # For now, return empty dict as Redis implementation is simplified
            return {}
        return dict(self._workers)

    # Job operations
    def upsert_job(self, job_id: str, info: Dict[str, Any]):
        if self._r:
            self._r.hset(f"job:{job_id}", mapping={k: str(v) for k, v in info.items()})
        else:
            self._jobs[job_id] = info

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self._r:
            data = self._r.hgetall(f"job:{job_id}")
            return data or None
        return self._jobs.get(job_id)
