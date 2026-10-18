import pandas as pd
from app.config import settings
from ml.inference.churn_predictor import ChurnPredictor


def predict_churn(df: pd.DataFrame) -> list[float]:
    """Get the churn score from MLflow Serving or explicit local-only mode."""
    return ChurnPredictor.predict(
        df,
        settings.MLFLOW_SERVING_URL,
        allow_local_inference=settings.MLFLOW_LOCAL_INFERENCE,
    )
