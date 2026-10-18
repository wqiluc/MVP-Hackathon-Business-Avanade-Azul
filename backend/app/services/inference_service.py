import pandas as pd
from app.config import settings
from ml.inference.churn_predictor import ChurnPredictor


def predict_churn(df: pd.DataFrame) -> list[float]:
    """Score de evasão 0–1 via MLflow Serving; fallback por regras se indisponível."""
    return ChurnPredictor.predict(df, settings.MLFLOW_SERVING_URL)
