from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Iterator

import mlflow
import mlflow.sklearn
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient


EXPERIMENT_NAME = "Azul_CRM_Churn_Prediction"
MODEL_ARTIFACT_PATH = "churn_rf_model"
MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "").strip()
MODEL_ALIAS = "champion"
SKOPS_TRUSTED_TYPES = ["sklearn.tree._tree.Tree"]


@dataclass(frozen=True)
class RegisteredChurnModel:
    model_name: str
    model_version: str
    alias: str
    run_id: str


@dataclass(frozen=True)
class ActiveChurnModel:
    model_name: str
    model_version: str
    alias: str
    run_id: str
    status: str
    metrics: dict[str, float]
    start_time: int


class MLflowChurnRun:
    def __init__(self, run) -> None:
        self._run = run

    @property
    def run_id(self) -> str:
        return self._run.info.run_id

    @staticmethod
    def log_training(
        model,
        params: dict[str, int],
        metrics: dict[str, float],
    ) -> str:
        mlflow.log_params(params)
        for name in ("accuracy", "precision", "recall"):
            mlflow.log_metric(name, float(metrics[name]))
        model_info = mlflow.sklearn.log_model(
            model,
                name=MODEL_ARTIFACT_PATH,
            pyfunc_predict_fn="predict_proba",
            skops_trusted_types=SKOPS_TRUSTED_TYPES,
        )
        return model_info.model_uri


def configure_tracking(tracking_uri: str) -> None:
    if not tracking_uri:
        raise ValueError("MLFLOW_TRACKING_URI deve estar configurado.")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)


def _client() -> MlflowClient:
    return MlflowClient(
        tracking_uri=mlflow.get_tracking_uri(),
        registry_uri=mlflow.get_registry_uri(),
    )


def set_churn_experiment() -> None:
    mlflow.set_experiment(EXPERIMENT_NAME)


def search_latest_churn_runs():
    return mlflow.search_runs(
        experiment_names=[EXPERIMENT_NAME],
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )


def register_churn_model(model_uri: str, run_id: str) -> RegisteredChurnModel:
    if not MODEL_NAME:
        raise ValueError("MLFLOW_MODEL_NAME deve estar configurado.")
    version = mlflow.register_model(model_uri, MODEL_NAME, await_registration_for=300)
    if version.status != "READY":
        raise RuntimeError(
            f"MLflow Model Registry não deixou a versão {version.version} pronta: "
            f"{version.status}."
        )
    if version.run_id != run_id:
        raise RuntimeError(
            f"MLflow registrou a versão {version.version} para o run inesperado "
            f"{version.run_id!r}; esperado {run_id!r}."
        )

    _client().set_registered_model_alias(MODEL_NAME, MODEL_ALIAS, version.version)
    active = _client().get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
    if active.version != version.version or active.run_id != run_id:
        raise RuntimeError("O alias champion não aponta para a versão recém-registrada.")

    return RegisteredChurnModel(
        model_name=version.name,
        model_version=version.version,
        alias=MODEL_ALIAS,
        run_id=version.run_id,
    )


def get_active_churn_model() -> ActiveChurnModel | None:
    if not MODEL_NAME:
        return None
    client = _client()
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
    except MlflowException as exc:
        if exc.error_code == "RESOURCE_DOES_NOT_EXIST":
            return None
        raise

    if version.status != "READY":
        raise RuntimeError(
            f"A versão ativa de {MODEL_NAME} não está pronta: {version.status}."
        )

    run = client.get_run(version.run_id)
    return ActiveChurnModel(
        model_name=version.name,
        model_version=version.version,
        alias=MODEL_ALIAS,
        run_id=version.run_id,
        status=version.status,
        metrics={key: float(value) for key, value in run.data.metrics.items()},
        start_time=run.info.start_time,
    )


@contextmanager
def start_churn_run() -> Iterator[MLflowChurnRun]:
    with mlflow.start_run() as run:
        yield MLflowChurnRun(run)
