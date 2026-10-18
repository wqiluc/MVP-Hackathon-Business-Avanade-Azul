from datetime import datetime, timezone

from app.config import settings
from app.services.datalake_service import DataLakeService
from ml.features.training_dataset import prepare_training_dataset
from ml.evaluation.metrics import calculate_classification_metrics
from ml.models.mlflow_tracker import (
    configure_tracking,
    get_active_churn_model,
    register_churn_model,
    set_churn_experiment,
    start_churn_run,
)
from ml.training.churn_trainer import CHURN_MODEL_PARAMETERS, train_churn_classifier


def get_active_model_info() -> dict:
    """Return the model information represented by the active Registry alias."""
    configure_tracking(settings.MLFLOW_TRACKING_URI)
    active = get_active_churn_model()
    if active is None:
        return {
            "nome": "Modelo de evasão (RandomForest)",
            "plataforma": "MLflow",
            "metaAcuracia": 0.9,
            "versao": "—",
            "status": "aguardando-registro",
            "acuracia": None,
            "auc": None,
            "treinadoEm": None,
        }

    trained_at = datetime.fromtimestamp(
        active.start_time / 1000,
        tz=timezone.utc,
    ).isoformat()
    return {
        "nome": active.model_name,
        "plataforma": "MLflow",
        "metaAcuracia": 0.9,
        "versao": active.model_version,
        "status": "em-producao",
        "acuracia": active.metrics.get("accuracy"),
        "auc": active.metrics.get("auc"),
        "treinadoEm": trained_at,
    }


def train_and_register_churn_model() -> dict:
    """
    Treina o modelo RandomForest sobre a camada Ouro e o publica no Model
    Registry do MLflow sob o alias ativo.
    """
    configure_tracking(settings.MLFLOW_TRACKING_URI)
    set_churn_experiment()

    df = DataLakeService.read_gold()

    if df.empty:
        raise ValueError(
            "A camada Ouro do Data Lake está vazia. Execute o upload de dados "
            "(/data/ingest) antes de treinar o modelo."
        )

    if len(df) < 5:
        raise ValueError(
            "Quantidade insuficiente de registros na camada Ouro para treinar "
            "o modelo (mínimo de 5 registros)."
        )

    features, target = prepare_training_dataset(df)

    with start_churn_run() as run:
        model, y_test, y_pred = train_churn_classifier(features, target)
        metrics = calculate_classification_metrics(y_test, y_pred)
        model_uri = run.log_training(model, CHURN_MODEL_PARAMETERS, metrics)
        registered = register_churn_model(model_uri, run.run_id)

    return {
        "run_id": registered.run_id,
        "accuracy": round(metrics["accuracy"], 4),
        "precision": round(metrics["precision"], 4),
        "recall": round(metrics["recall"], 4),
        "status": (
            f"Modelo {registered.model_name} v{registered.model_version} "
            f"registrado como {registered.alias} no MLflow"
        ),
    }
