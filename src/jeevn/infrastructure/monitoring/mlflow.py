"""
MLflow integration for experiment tracking.
"""

import os
from typing import Dict, Any


def setup_mlflow():
    """Initialize MLflow tracking."""
    try:
        import mlflow

        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        return mlflow
    except ImportError:
        return None


def log_dummy_run(
    params: Dict[str, Any] = None,
    metrics: Dict[str, float] = None,
    artifacts: list = None
):
    """Log a sample run to MLflow."""
    try:
        import mlflow
    except ImportError:
        print("[WARN] MLflow not available")
        return

    try:
        mlflow.start_run()

        if params:
            for key, value in params.items():
                mlflow.log_param(key, value)

        if metrics:
            for key, value in metrics.items():
                mlflow.log_metric(key, value)

        if artifacts:
            for artifact_path in artifacts:
                if os.path.exists(artifact_path):
                    mlflow.log_artifact(artifact_path)

        mlflow.end_run()

    except Exception as e:
        print(f"[WARN] MLflow logging failed: {e}")
