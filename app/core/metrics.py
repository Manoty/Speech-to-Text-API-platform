"""
app/core/metrics.py

Prometheus metrics setup via prometheus-fastapi-instrumentator.

Exposes /metrics endpoint with:
- http_requests_total (counter, by method/path/status)
- http_request_duration_seconds (histogram)
- http_requests_in_progress (gauge)

Custom business metrics:
- transcription_jobs_total (counter, by status)
- transcription_duration_seconds (histogram)
- active_websocket_connections (gauge)

WHY Prometheus over custom logging metrics?
Prometheus + Grafana is the industry standard.
Scraped by any monitoring stack (Grafana Cloud, Datadog, etc.)
Time-series data enables alerting on error rate spikes.
"""

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ── Custom business metrics ──────────────────────────────────

transcription_jobs_total = Counter(
    "transcription_jobs_total",
    "Total transcription jobs by status",
    ["status"],  # completed, failed, pending
)

transcription_duration_seconds = Histogram(
    "transcription_duration_seconds",
    "Audio duration of transcribed files in seconds",
    buckets=[30, 60, 120, 300, 600, 1200, 3600],
)

transcription_processing_seconds = Histogram(
    "transcription_processing_seconds",
    "Time taken to process a transcription",
    buckets=[5, 10, 30, 60, 120, 300, 600],
)

active_websocket_connections = Gauge(
    "active_websocket_connections",
    "Number of active WebSocket connections",
)

file_upload_size_bytes = Histogram(
    "file_upload_size_bytes",
    "Size of uploaded audio files",
    buckets=[
        1_000_000,    # 1MB
        10_000_000,   # 10MB
        50_000_000,   # 50MB
        100_000_000,  # 100MB
        500_000_000,  # 500MB
    ],
)


def setup_metrics(app) -> None:
    """
    Attach Prometheus instrumentator to FastAPI app.
    Call once in create_app().
    """
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)