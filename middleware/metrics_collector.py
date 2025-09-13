"""
Monitoring and Metrics System for Poneglyph Middleware
Collects and exposes system metrics, performance data, and health information
"""

import time
import json
import threading
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: int
    value: float
    labels: Dict[str, str] = None

@dataclass
class WorkerMetrics:
    """Worker-specific metrics"""
    worker_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_task_duration: float = 0.0
    last_heartbeat: int = 0
    health_score: float = 100.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

@dataclass
class JobMetrics:
    """Job-specific metrics"""
    job_id: str
    state: str = "PENDING"
    created_at: int = 0
    started_at: int = 0
    completed_at: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    progress_percentage: float = 0.0
    estimated_completion: int = 0

@dataclass
class SystemMetrics:
    """Overall system metrics"""
    active_workers: int = 0
    total_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    avg_job_duration: float = 0.0
    throughput_tasks_per_second: float = 0.0
    resource_utilization: float = 0.0

class MetricsCollector:
    """Centralized metrics collection and storage"""
    
    def __init__(self, retention_minutes: int = 60):
        self.retention_minutes = retention_minutes
        self.retention_ms = retention_minutes * 60 * 1000
        
        # Time-series storage for metrics
        self.time_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Current snapshots
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.job_metrics: Dict[str, JobMetrics] = {}
        self.system_metrics = SystemMetrics()
        
        # Counters and gauges
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        
        # Performance tracking
        self.task_durations = deque(maxlen=100)  # Last 100 task durations
        self.job_durations = deque(maxlen=50)    # Last 50 job durations
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Background cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._running = True
        self._cleanup_thread.start()

    def record_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Record a counter metric (cumulative)"""
        with self._lock:
            self.counters[name] += value
            self._add_time_series_point(f"counter.{name}", value, labels)

    def record_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a gauge metric (current value)"""
        with self._lock:
            self.gauges[name] = value
            self._add_time_series_point(f"gauge.{name}", value, labels)

    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram metric (distribution of values)"""
        with self._lock:
            # Store individual points for histogram analysis
            self._add_time_series_point(f"histogram.{name}", value, labels)
            
            # Update running statistics
            if name == "task_duration_ms":
                self.task_durations.append(value)
            elif name == "job_duration_ms":
                self.job_durations.append(value)

    def _add_time_series_point(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Add a point to time series storage"""
        point = MetricPoint(
            timestamp=int(time.time() * 1000),
            value=value,
            labels=labels or {}
        )
        self.time_series[metric_name].append(point)

    # Worker metrics methods
    def update_worker_metrics(self, worker_id: str, **kwargs):
        """Update metrics for a specific worker"""
        with self._lock:
            if worker_id not in self.worker_metrics:
                self.worker_metrics[worker_id] = WorkerMetrics(worker_id=worker_id)
            
            worker = self.worker_metrics[worker_id]
            for key, value in kwargs.items():
                if hasattr(worker, key):
                    setattr(worker, key, value)
            
            # Update last heartbeat timestamp
            worker.last_heartbeat = int(time.time() * 1000)

    def record_task_completion(self, worker_id: str, job_id: str, success: bool, duration_ms: float):
        """Record task completion metrics"""
        with self._lock:
            # Update worker metrics
            if worker_id in self.worker_metrics:
                worker = self.worker_metrics[worker_id]
                if success:
                    worker.tasks_completed += 1
                    self.record_counter("tasks_completed", labels={"worker_id": worker_id})
                else:
                    worker.tasks_failed += 1
                    self.record_counter("tasks_failed", labels={"worker_id": worker_id})
                
                # Update average task duration
                total_tasks = worker.tasks_completed + worker.tasks_failed
                if total_tasks > 0:
                    current_avg = worker.avg_task_duration
                    worker.avg_task_duration = ((current_avg * (total_tasks - 1)) + duration_ms) / total_tasks
            
            # Record system-wide metrics
            self.record_histogram("task_duration_ms", duration_ms, {"worker_id": worker_id, "job_id": job_id})
            self.record_counter("tasks_total", labels={"success": str(success)})

    def record_job_state_change(self, job_id: str, old_state: str, new_state: str):
        """Record job state transitions"""
        with self._lock:
            current_time = int(time.time() * 1000)
            
            if job_id not in self.job_metrics:
                self.job_metrics[job_id] = JobMetrics(job_id=job_id, created_at=current_time)
            
            job = self.job_metrics[job_id]
            job.state = new_state
            
            if new_state == "RUNNING" and job.started_at == 0:
                job.started_at = current_time
            elif new_state in ["COMPLETED", "FAILED"] and job.completed_at == 0:
                job.completed_at = current_time
                
                # Calculate job duration
                if job.started_at > 0:
                    duration = job.completed_at - job.started_at
                    self.record_histogram("job_duration_ms", duration, {"job_id": job_id, "state": new_state})
            
            # Record state transition
            self.record_counter("job_state_transitions", labels={"from": old_state, "to": new_state})

    def update_job_progress(self, job_id: str, total_tasks: int, completed_tasks: int, failed_tasks: int):
        """Update job progress metrics"""
        with self._lock:
            if job_id in self.job_metrics:
                job = self.job_metrics[job_id]
                job.total_tasks = total_tasks
                job.completed_tasks = completed_tasks
                job.failed_tasks = failed_tasks
                
                if total_tasks > 0:
                    job.progress_percentage = (completed_tasks / total_tasks) * 100
                
                # Estimate completion time based on current rate
                if completed_tasks > 0 and job.started_at > 0:
                    current_time = int(time.time() * 1000)
                    elapsed = current_time - job.started_at
                    rate = completed_tasks / elapsed if elapsed > 0 else 0
                    
                    if rate > 0:
                        remaining_tasks = total_tasks - completed_tasks
                        estimated_remaining_ms = remaining_tasks / rate
                        job.estimated_completion = int(current_time + estimated_remaining_ms)

    def get_system_metrics(self) -> SystemMetrics:
        """Calculate and return current system metrics"""
        with self._lock:
            current_time = int(time.time() * 1000)
            ttl_threshold = current_time - 60000  # 1 minute TTL
            
            # Count active workers
            active_workers = sum(1 for w in self.worker_metrics.values() 
                               if w.last_heartbeat > ttl_threshold)
            
            # Count jobs by state
            running_jobs = sum(1 for j in self.job_metrics.values() if j.state == "RUNNING")
            completed_jobs = sum(1 for j in self.job_metrics.values() if j.state == "COMPLETED")
            failed_jobs = sum(1 for j in self.job_metrics.values() if j.state == "FAILED")
            total_jobs = len(self.job_metrics)
            
            # Calculate average job duration
            avg_job_duration = 0.0
            if self.job_durations:
                avg_job_duration = sum(self.job_durations) / len(self.job_durations)
            
            # Calculate throughput (tasks per second over last minute)
            throughput = self._calculate_throughput()
            
            # Calculate resource utilization
            resource_utilization = self._calculate_resource_utilization()
            
            self.system_metrics = SystemMetrics(
                active_workers=active_workers,
                total_jobs=total_jobs,
                running_jobs=running_jobs,
                completed_jobs=completed_jobs,
                failed_jobs=failed_jobs,
                avg_job_duration=avg_job_duration,
                throughput_tasks_per_second=throughput,
                resource_utilization=resource_utilization
            )
            
            return self.system_metrics

    def _calculate_throughput(self) -> float:
        """Calculate tasks per second over the last minute"""
        current_time = int(time.time() * 1000)
        one_minute_ago = current_time - 60000
        
        task_points = self.time_series.get("counter.tasks_completed", deque())
        recent_tasks = [p for p in task_points if p.timestamp > one_minute_ago]
        
        if len(recent_tasks) < 2:
            return 0.0
        
        total_tasks = sum(p.value for p in recent_tasks)
        time_span_seconds = (recent_tasks[-1].timestamp - recent_tasks[0].timestamp) / 1000
        
        return total_tasks / time_span_seconds if time_span_seconds > 0 else 0.0

    def _calculate_resource_utilization(self) -> float:
        """Calculate overall resource utilization percentage"""
        if not self.worker_metrics:
            return 0.0
        
        current_time = int(time.time() * 1000)
        ttl_threshold = current_time - 60000
        
        active_workers = [w for w in self.worker_metrics.values() 
                         if w.last_heartbeat > ttl_threshold]
        
        if not active_workers:
            return 0.0
        
        total_capacity = sum(getattr(w, 'capacity', 1) for w in active_workers)
        total_utilization = sum(getattr(w, 'cpu_usage', 0) for w in active_workers)
        
        return (total_utilization / total_capacity) * 100 if total_capacity > 0 else 0.0

    def get_time_series_data(self, metric_name: str, start_time: int = None, end_time: int = None) -> List[MetricPoint]:
        """Get time series data for a specific metric"""
        with self._lock:
            points = list(self.time_series.get(metric_name, []))
            
            if start_time:
                points = [p for p in points if p.timestamp >= start_time]
            if end_time:
                points = [p for p in points if p.timestamp <= end_time]
            
            return points

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        with self._lock:
            lines = []
            current_time = int(time.time() * 1000)
            
            # System metrics
            system = self.get_system_metrics()
            lines.append(f"# HELP poneglyph_active_workers Number of active workers")
            lines.append(f"# TYPE poneglyph_active_workers gauge")
            lines.append(f"poneglyph_active_workers {system.active_workers} {current_time}")
            
            lines.append(f"# HELP poneglyph_running_jobs Number of running jobs")
            lines.append(f"# TYPE poneglyph_running_jobs gauge")
            lines.append(f"poneglyph_running_jobs {system.running_jobs} {current_time}")
            
            lines.append(f"# HELP poneglyph_throughput_tasks_per_second Task throughput")
            lines.append(f"# TYPE poneglyph_throughput_tasks_per_second gauge")
            lines.append(f"poneglyph_throughput_tasks_per_second {system.throughput_tasks_per_second} {current_time}")
            
            # Counters
            for name, value in self.counters.items():
                metric_name = f"poneglyph_{name.replace('.', '_')}"
                lines.append(f"# HELP {metric_name} Counter metric")
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {value} {current_time}")
            
            # Gauges
            for name, value in self.gauges.items():
                metric_name = f"poneglyph_{name.replace('.', '_')}"
                lines.append(f"# HELP {metric_name} Gauge metric")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {value} {current_time}")
            
            return "\n".join(lines)

    def export_json_summary(self) -> Dict[str, Any]:
        """Export a JSON summary of all metrics"""
        with self._lock:
            return {
                "timestamp": int(time.time() * 1000),
                "system_metrics": asdict(self.get_system_metrics()),
                "worker_metrics": {wid: asdict(worker) for wid, worker in self.worker_metrics.items()},
                "job_metrics": {jid: asdict(job) for jid, job in self.job_metrics.items()},
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "performance_summary": {
                    "avg_task_duration_ms": sum(self.task_durations) / len(self.task_durations) if self.task_durations else 0,
                    "avg_job_duration_ms": sum(self.job_durations) / len(self.job_durations) if self.job_durations else 0,
                    "total_time_series_points": sum(len(ts) for ts in self.time_series.values())
                }
            }

    def _cleanup_loop(self):
        """Background thread to cleanup old metrics data"""
        while self._running:
            try:
                current_time = int(time.time() * 1000)
                cutoff_time = current_time - self.retention_ms
                
                with self._lock:
                    # Clean up time series data
                    for metric_name, points in self.time_series.items():
                        while points and points[0].timestamp < cutoff_time:
                            points.popleft()
                    
                    # Clean up stale worker metrics
                    stale_workers = [wid for wid, worker in self.worker_metrics.items()
                                   if worker.last_heartbeat < cutoff_time]
                    for wid in stale_workers:
                        del self.worker_metrics[wid]
                
                # Sleep for 30 seconds before next cleanup
                time.sleep(30)
                
            except Exception as e:
                print(f"Metrics cleanup error: {e}")
                time.sleep(60)  # Wait longer on error

    def stop(self):
        """Stop the metrics collector"""
        self._running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)

# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector

def initialize_metrics(retention_minutes: int = 60):
    """Initialize the global metrics collector"""
    global _global_collector
    if _global_collector:
        _global_collector.stop()
    _global_collector = MetricsCollector(retention_minutes)
    return _global_collector
