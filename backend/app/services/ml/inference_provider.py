import json
import logging
import subprocess
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
        python_executables: dict[str, str] | None = None,
        timeout_seconds: float = 120.0,
    ):
        self.model_paths = model_paths
        self.model_loader = model_loader
        self.python_executables = {
            key: value.strip()
            for key, value in (python_executables or {}).items()
            if value and value.strip()
        }
        self.timeout_seconds = timeout_seconds

    def _model_path(self, model_key: str) -> Path:
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
        return path

    def _python_executable(self, model_key: str) -> Path:
        path = Path(self.python_executables[model_key]).expanduser()
        if not path.is_absolute():
            from app.config import BASE_DIR

            path = BASE_DIR / path
        # Sem resolve(): o python de um venv é symlink e precisa manter o caminho do venv.
        if not path.is_file():
            raise ModelInferenceError(
                f"ML_{model_key.upper()}_PYTHON is configured but the interpreter "
                "is unavailable."
            )
        return path

    def _predict_isolated(
        self, model_key: str, path: Path, frame: pd.DataFrame, method: str
    ) -> tuple[Any, tuple[Any, ...] | None]:
        payload = json.dumps(
            {
                "model_path": str(path),
                "method": method,
                "frame": json.loads(frame.to_json(orient="split", index=False)),
            }
        )
        worker = Path(__file__).with_name("isolated_model_worker.py")
        try:
            completed = subprocess.run(
                [str(self._python_executable(model_key)), str(worker)],
                input=payload,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ModelInferenceError(
                f"Isolated {model_key} inference timed out."
            ) from exc
        except OSError as exc:
            raise ModelInferenceError(
                f"Isolated {model_key} interpreter could not be started "
                f"({type(exc).__name__})."
            ) from exc
        if completed.returncode != 0:
            logger.warning(
                "Isolated model worker failed model_key=%s returncode=%s",
                model_key,
                completed.returncode,
            )
            raise ModelInferenceError(
                f"Isolated {model_key} model execution failed."
            )
        try:
            body = json.loads(completed.stdout)
            predictions = body["predictions"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ModelInferenceError(
                f"Isolated {model_key} worker returned an invalid response."
            ) from exc
        classes = body.get("classes")
        return predictions, tuple(classes) if classes is not None else None

    def _load(self, model_key: str):
        path = self._model_path(model_key)
        cache_key = str(path)
        with self._model_lock:
            if cache_key not in self._models:
                logger.info("Loading local MLflow model model_key=%s", model_key)
                try:
                    if self.model_loader is None:
                        import mlflow.sklearn

                        self._models[cache_key] = mlflow.sklearn.load_model(cache_key)
                    else:
                        self._models[cache_key] = self.model_loader(cache_key)
                except Exception as exc:
                    logger.warning(
                        "Local model load failed model_key=%s error_type=%s",
                        model_key,
                        type(exc).__name__,
                    )
                    raise ModelInferenceError(
                        f"Local {model_key} model could not be loaded "
                        f"({type(exc).__name__})."
                    ) from exc
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
        if model_key in self.python_executables:
            path = self._model_path(model_key)
            model_name, model_version = self._artifact_metadata(path)
            predictions, classes = self._predict_isolated(
                model_key, path, frame, method
            )
            return InferenceResult(
                predictions=predictions,
                classes=classes,
                model_name=model_name,
                model_version=model_version,
                source=self.source,
            )
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
        hosts: dict[str, str],
        tokens: dict[str, str],
        endpoints: dict[str, str],
        timeout_seconds: float,
        class_orders: dict[str, tuple[Any, ...]] | None = None,
    ):
        self.hosts = {
            key: value.rstrip("/")
            for key, value in hosts.items()
        }
        self.tokens = tokens
        self.endpoints = endpoints
        self.timeout_seconds = timeout_seconds
        self.class_orders = class_orders or {}

    def predict(
        self, model_key: str, frame: pd.DataFrame, method: str
    ) -> InferenceResult:
        del method
        host = self.hosts.get(model_key, "").strip()
        token = self.tokens.get(model_key, "").strip()
        endpoint = self.endpoints.get(model_key, "").strip()

        if not host or not token or not endpoint:
            raise ModelInferenceError(
                f"Databricks host, token, and {model_key} endpoint are required."
            )
        url = (
            f"{host}/api/2.0/serving-endpoints/"
            f"{quote(endpoint, safe='')}/invocations"
        )
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
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
            },
            python_executables={
                "churn": settings.ML_CHURN_PYTHON,
                "clv": settings.ML_CLV_PYTHON,
            },
            timeout_seconds=settings.ML_ISOLATED_TIMEOUT_SECONDS,
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
            hosts={
                "churn": settings.DATABRICKS_CHURN_HOST,
                "clv": settings.DATABRICKS_CLV_HOST,
            },
            tokens={
                "churn": settings.DATABRICKS_CHURN_TOKEN,
                "clv": settings.DATABRICKS_CLV_TOKEN,
            },
            endpoints={
                "churn": settings.DATABRICKS_CHURN_ENDPOINT,
                "clv": settings.DATABRICKS_CLV_ENDPOINT,
            },
            timeout_seconds=settings.ML_INFERENCE_TIMEOUT_SECONDS,
            class_orders={"churn": churn_classes},
        )
    raise ModelInferenceError("ML_INFERENCE_MODE must be local or databricks.")


def get_inference_provider() -> ModelInferenceProvider:
    return _settings_provider()
