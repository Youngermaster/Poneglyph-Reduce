"""
HTTP Metrics Server for Poneglyph Middleware
Exposes metrics via HTTP endpoints for monitoring systems like Prometheus
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from middleware.metrics_collector import get_metrics_collector

class MetricsHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for metrics endpoints"""
    
    def do_GET(self):
        """Handle GET requests for metrics"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query_params = parse_qs(parsed_path.query)
            
            metrics = get_metrics_collector()
            
            if path == "/metrics":
                # Prometheus format metrics
                self._serve_prometheus_metrics(metrics)
            elif path == "/metrics/json":
                # JSON format metrics
                self._serve_json_metrics(metrics)
            elif path == "/health":
                # Health check endpoint
                self._serve_health_check(metrics)
            elif path == "/metrics/timeseries":
                # Time series data for specific metric
                self._serve_timeseries_data(metrics, query_params)
            elif path == "/loadbalancer" or path == "/loadbalancer/stats":
                # Load balancer statistics
                self._serve_loadbalancer_stats()
            elif path == "/":
                # Basic info page
                self._serve_info_page()
            else:
                self._send_error(404, "Not Found")
        except Exception as e:
            self._send_error(500, f"Internal Server Error: {str(e)}")
    
    def _serve_prometheus_metrics(self, metrics):
        """Serve metrics in Prometheus format"""
        prometheus_data = metrics.export_prometheus_metrics()
        self._send_response(200, prometheus_data, "text/plain; version=0.0.4; charset=utf-8")
    
    def _serve_json_metrics(self, metrics):
        """Serve metrics in JSON format"""
        json_data = metrics.export_json_summary()
        response_body = json.dumps(json_data, indent=2)
        self._send_response(200, response_body, "application/json")
    
    def _serve_health_check(self, metrics):
        """Serve health check information"""
        system_metrics = metrics.get_system_metrics()
        
        # Determine health status
        health_status = "healthy"
        if system_metrics.active_workers == 0:
            health_status = "degraded"
        elif system_metrics.resource_utilization > 90:
            health_status = "overloaded"
        
        health_data = {
            "status": health_status,
            "timestamp": metrics.export_json_summary()["timestamp"],
            "active_workers": system_metrics.active_workers,
            "running_jobs": system_metrics.running_jobs,
            "resource_utilization": system_metrics.resource_utilization,
            "throughput": system_metrics.throughput_tasks_per_second
        }
        
        status_code = 200 if health_status == "healthy" else 503
        response_body = json.dumps(health_data, indent=2)
        self._send_response(status_code, response_body, "application/json")
    
    def _serve_loadbalancer_stats(self):
        """Serve load balancer statistics"""
        try:
            from middleware.load_balancer import get_load_balancer
            load_balancer = get_load_balancer()
            stats = load_balancer.get_worker_statistics()
            
            response_body = json.dumps(stats, indent=2)
            self._send_response(200, response_body, "application/json")
        except Exception as e:
            self._send_error(500, f"Load balancer error: {str(e)}")
    
    def _serve_timeseries_data(self, metrics, query_params):
        """Serve time series data for a specific metric"""
        metric_name = query_params.get('metric', [''])[0]
        start_time = query_params.get('start', [None])[0]
        end_time = query_params.get('end', [None])[0]
        
        if not metric_name:
            self._send_error(400, "Missing 'metric' parameter")
            return
        
        try:
            start_time = int(start_time) if start_time else None
            end_time = int(end_time) if end_time else None
        except ValueError:
            self._send_error(400, "Invalid time parameters")
            return
        
        time_series = metrics.get_time_series_data(metric_name, start_time, end_time)
        
        # Convert to simple format
        data_points = [
            {"timestamp": point.timestamp, "value": point.value, "labels": point.labels}
            for point in time_series
        ]
        
        response_data = {
            "metric": metric_name,
            "start_time": start_time,
            "end_time": end_time,
            "data_points": data_points,
            "count": len(data_points)
        }
        
        response_body = json.dumps(response_data, indent=2)
        self._send_response(200, response_body, "application/json")
    
    def _serve_info_page(self):
        """Serve basic information page"""
        metrics = get_metrics_collector()
        system_metrics = metrics.get_system_metrics()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Poneglyph Middleware Metrics</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .metric {{ margin: 10px 0; }}
                .endpoint {{ background: #f0f0f0; padding: 10px; margin: 5px 0; }}
                .value {{ font-weight: bold; color: #0066cc; }}
            </style>
        </head>
        <body>
            <h1>Poneglyph Middleware Metrics</h1>
            
            <h2>System Overview</h2>
            <div class="metric">Active Workers: <span class="value">{system_metrics.active_workers}</span></div>
            <div class="metric">Running Jobs: <span class="value">{system_metrics.running_jobs}</span></div>
            <div class="metric">Completed Jobs: <span class="value">{system_metrics.completed_jobs}</span></div>
            <div class="metric">Throughput: <span class="value">{system_metrics.throughput_tasks_per_second:.2f} tasks/sec</span></div>
            <div class="metric">Resource Utilization: <span class="value">{system_metrics.resource_utilization:.1f}%</span></div>
            
            <h2>Available Endpoints</h2>
            <div class="endpoint">
                <strong>GET /metrics</strong><br>
                Prometheus format metrics for scraping
            </div>
            <div class="endpoint">
                <strong>GET /metrics/json</strong><br>
                Complete metrics in JSON format
            </div>
            <div class="endpoint">
                <strong>GET /health</strong><br>
                Health check endpoint
            </div>
            <div class="endpoint">
                <strong>GET /metrics/timeseries?metric=METRIC_NAME&start=TIMESTAMP&end=TIMESTAMP</strong><br>
                Time series data for specific metrics
            </div>
            <div class="endpoint">
                <strong>GET /loadbalancer</strong><br>
                Load balancer statistics and worker performance metrics
            </div>
            
            <p><em>Last updated: {metrics.export_json_summary()["timestamp"]}</em></p>
        </body>
        </html>
        """
        
        self._send_response(200, html_content, "text/html")
    
    def _send_response(self, status_code, body, content_type="text/plain"):
        """Send HTTP response"""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body.encode('utf-8'))))
        self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))
    
    def _send_error(self, status_code, message):
        """Send error response"""
        error_data = {"error": message, "status_code": status_code}
        body = json.dumps(error_data)
        self._send_response(status_code, body, "application/json")
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

class MetricsHTTPServer:
    """HTTP server for metrics endpoints"""
    
    def __init__(self, port: int = 8080, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.server = None
        self.thread = None
        self._running = False
    
    def start(self):
        """Start the HTTP server in a background thread"""
        if self._running:
            return
        
        self.server = HTTPServer((self.host, self.port), MetricsHTTPHandler)
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self._running = True
        self.thread.start()
        print(f"Metrics HTTP server started on http://{self.host}:{self.port}")
    
    def _run_server(self):
        """Run the HTTP server"""
        try:
            while self._running:
                self.server.handle_request()
        except Exception as e:
            print(f"Metrics HTTP server error: {e}")
    
    def stop(self):
        """Stop the HTTP server"""
        self._running = False
        if self.server:
            self.server.server_close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
