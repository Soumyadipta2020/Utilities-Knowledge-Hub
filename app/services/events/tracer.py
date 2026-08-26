import contextvars
import time
import uuid
from typing import Any, Dict, Optional

# Context variable for the current request ID
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="unknown")
_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="system")

class RequestContext:
    """Manages context and telemetry for a single request."""
    def __init__(self, user_id: str, request_id: Optional[str] = None):
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id
        self.start_time = time.time()
        self.metrics: Dict[str, Any] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tools_executed": 0,
            "total_rows_returned": 0,
            "errors": 0,
            "latency_ms": {}
        }
        self.token = None
        self.user_token = None

    def __enter__(self):
        self.token = _request_id_var.set(self.request_id)
        self.user_token = _user_id_var.set(self.user_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            _request_id_var.reset(self.token)
        if self.user_token:
            _user_id_var.reset(self.user_token)
            
        total_time_ms = (time.time() - self.start_time) * 1000
        self.metrics["total_latency_ms"] = total_time_ms
        if exc_type:
            self.metrics["errors"] += 1

    def record_latency(self, stage: str, duration_ms: float):
        self.metrics["latency_ms"][stage] = duration_ms

    def record_cache_hit(self):
        self.metrics["cache_hits"] += 1
        
    def record_cache_miss(self):
        self.metrics["cache_misses"] += 1
        
    def record_tool_execution(self, rows_returned: int = 0):
        self.metrics["tools_executed"] += 1
        self.metrics["total_rows_returned"] += rows_returned

def get_current_request_id() -> str:
    return _request_id_var.get()

def get_current_user_id() -> str:
    return _user_id_var.get()
