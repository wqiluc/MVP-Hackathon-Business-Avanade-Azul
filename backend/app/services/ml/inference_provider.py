import logging
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Protocol
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import yaml

logger = logging.getLogger(__name__)


class ModelInferenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class InferenceResult:
    predictions: Any
    classes: tuple[Any, ...] | None
    model_name: str
    model_version: str | None
    source: str


class ModelInferenceProvider(Protocol):
    source: str

    def predict(
        self, model_key: str, frame: pd.DataFrame, method: str
    ) -> InferenceResult: ...


class LocalMLflowInferenceProvider:
    source = "local"
    _models: dict[str, Any] = {}
    _model_lock = RLock()

    def __init__(
        self,
        model_paths: dict[str, str],
        model_loader: Callable[[str], Any] | None = None,
    ):
        self.model_paths = model_paths
        self.model_loader = model_loader

    def _load(self, model_key: str):
        configured_path = self.model_paths.get(model_key, "").strip()
        if not configured_path:
            raise ModelInferenceError(
                f"ML_{model_key.upper()}_MODEL_PATH is required for local inference."
            )
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            from app.config import BASE_DIR

            path = BASE_DIR / path
        path = path.resolve()
        if not path.is_dir():
            raise ModelInferenceError("Configured local MLflow model path is unavailable.")

        cache_key = str(path)
        with self._model_lock:
            if cache_key not in self._models:
                logger.info("Loading local MLflow model model_key=%s", model_key)
                if self.model_loader is None:
                    import mlflow.sklearn

                    self._models[cache_key] = mlflow.sklearn.load_model(cache_key)
                else:
                    self._models[cache_key] = self.model_loader(cache_key)
        return self._models[cache_key], path

    @staticmethod
    def _artifact_metadata(path: Path) -> tuple[str, str | None]:
        metadata_file = path / "registered_model_meta"
        if not metadata_file.is_file():
            return path.name, None
        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ModelInferenceError(
                "Could not read the local model's registered metadata."
            ) from exc
        if not isinstance(metadata, dict):
            raise ModelInferenceError("Local model metadata has an invalid format.")
        return (
            str(metadata.get("model_name") or path.name),
            str(metadata["model_version"])
            if metadata.get("model_version") is not None
            else None,
        )

    def predict(
        self, model_key: str, frame: pd.DataFrame, method: str
    ) -> InferenceResult:
        model, path = self._load(model_key)
        predictor = getattr(model, method, None)
        if not callable(predictor):
            raise ModelInferenceError(
                f"Configured local {model_key} model does not support {method}."
            )
        model_name, model_version = self._artifact_metadata(path)
        return InferenceResult(
            predictions=predictor(frame),
            classes=tuple(np.asarray(model.classes_).tolist())
            if hasattr(model, "classes_")
            else None,
            model_name=model_name,
            model_version=model_version,
            source=self.source,
        )


class DatabricksServingInferenceProvider:
    source = "databricks"

    def __init__(
        self,
        host: str,
        token: str,
        endpoints: dict[str, str],
        timeout_seconds: float,
        class_orders: dict[str, tuple[Any, ...]] | None = None,
    ):
        self.host = host.rstrip("/")
        self.token = token
        self.endpoints = endpoints
        self.timeout_seconds = timeout_seconds
        self.class_orders = class_orders or {}

    def predict(
        self, model_key: str, frame: pd.DataFrame, method: str
    ) -> InferenceResult:
        del method
        endpoint = self.endpoints.get(model_key, "").strip()
        if not self.host or not self.token or not endpoint:
            raise ModelInferenceError(
                f"Databricks host, token, and {model_key} endpoint are required."
            )
        url = (
            f"{self.host}/api/2.0/serving-endpoints/"
            f"{quote(endpoint, safe='')}/invocations"
        )
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                json={"dataframe_split": frame.to_dict(orient="split")},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except requests.Timeout as exc:
            raise ModelInferenceError("Databricks inference timed out.") from exc
        except requests.RequestException as exc:
            raise ModelInferenceError(
                f"Databricks inference request failed ({type(exc).__name__})."
            ) from exc
        except ValueError as exc:
            raise ModelInferenceError(
                "Databricks returned invalid JSON for model inference."
            ) from exc

        if not isinstance(body, dict) or "predictions" not in body:
            raise ModelInferenceError(
                "Databricks response must contain a predictions field."
            )
        return InferenceResult(
            predictions=body["predictions"],
            classes=self.class_orders.get(model_key),
            model_name=endpoint,
            model_version=None,
            source=self.source,
        )


def _settings_provider():
    from app.config import settings

    if settings.ML_INFERENCE_MODE == "local":
        return LocalMLflowInferenceProvider(
            {
                "churn": settings.ML_CHURN_MODEL_PATH,
                "clv": settings.ML_CLV_MODEL_PATH,
            }
        )
    if settings.ML_INFERENCE_MODE == "databricks":
        try:
            churn_classes = tuple(
                int(value.strip())
                for value in settings.ML_CHURN_CLASS_ORDER.split(",")
                if value.strip()
            )
        except ValueError as exc:
            raise ModelInferenceError(
                "ML_CHURN_CLASS_ORDER must be a comma-separated list of integers."
            ) from exc
        if len(churn_classes) != 2 or len(set(churn_classes)) != 2:
            raise ModelInferenceError(
                "ML_CHURN_CLASS_ORDER must define exactly two distinct classes."
            )
        return DatabricksServingInferenceProvider(
            settings.DATABRICKS_HOST,
            settings.DATABRICKS_TOKEN,
            {
                "churn": settings.DATABRICKS_CHURN_ENDPOINT,
                "clv": settings.DATABRICKS_CLV_ENDPOINT,
            },
            settings.ML_INFERENCE_TIMEOUT_SECONDS,
            {"churn": churn_classes},
        )
    raise ModelInferenceError("ML_INFERENCE_MODE must be local or databricks.")


def get_inference_provider() -> ModelInferenceProvider:
    return _settings_provider()
