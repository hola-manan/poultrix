"""
Infrastructure layer — DB, monitoring, external data adapters,
and pseudo-satellite fallback constants.

Submodules are imported on demand so that consumers (e.g. the Streamlit UI)
that only need `pseudo_satellite` do not pull in side-effects from `monitoring`
(Prometheus metric registration) or `db` (SQLAlchemy engine creation).
"""

from . import pseudo_satellite  # constants-only, no side effects

__all__ = ["pseudo_satellite"]
