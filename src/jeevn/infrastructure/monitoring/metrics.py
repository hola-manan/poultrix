"""
Prometheus metrics for monitoring.

We register into a *private* CollectorRegistry rather than the global
prometheus_client REGISTRY. This isolates our metrics from any other library
using prometheus_client in the same process, and — critically — makes the
module safe to re-import (e.g. under Streamlit's in-process hot reload):
each fresh import creates a fresh registry, so there is no collision.
"""

from prometheus_client import Counter, Histogram, CollectorRegistry, make_asgi_app


_registry = CollectorRegistry()

aoi_created_counter = Counter(
    'ashi_aoi_created_total',
    'Total number of AOIs created',
    ['status'],
    registry=_registry,
)

aoi_error_counter = Counter(
    'ashi_aoi_errors_total',
    'Total number of AOI creation errors',
    registry=_registry,
)

request_duration_histogram = Histogram(
    'ashi_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint'],
    registry=_registry,
)

metrics_app = make_asgi_app(registry=_registry)
