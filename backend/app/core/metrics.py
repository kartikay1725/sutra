import threading
import time
from typing import Dict


class MetricsCollector:
    """Thread-safe, bounded Prometheus-compatible metrics collector for SUTRA."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "http_requests_total": 0,
            "http_requests_2xx_total": 0,
            "http_requests_4xx_total": 0,
            "http_requests_5xx_total": 0,
            "git_merges_total": 0,
            "git_cas_failures_total": 0,
            "ci_jobs_total": 0,
            "ci_sandbox_failures_total": 0,
            "tasks_completed_total": 0,
            "reconciliation_events_total": 0,
        }

    def increment(self, metric_name: str, value: int = 1) -> None:
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += value
            else:
                # Bounded key insertion fallback
                if len(self._counters) < 100:
                    self._counters[metric_name] = value

    def get_metrics_formatted(self) -> str:
        with self._lock:
            lines = ["# HELP sutra_metrics Operational metrics for SUTRA platform", "# TYPE sutra_metrics counter"]
            for name, val in sorted(self._counters.items()):
                lines.append(f"sutra_{name} {val}")
            return "\n".join(lines) + "\n"


metrics_collector = MetricsCollector()
