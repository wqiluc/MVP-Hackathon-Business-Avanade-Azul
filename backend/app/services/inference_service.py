import numpy as np
import pandas as pd
import requests
from app.config import settings

FEATURES = ["frequency", "recency_days", "total_spend", "flight_incidents", "avg_ticket"]


def _rules(df: pd.DataFrame) -> np.ndarray:
    """Probabilidade de evasão (0–1) por regras, usada sem MLflow Serving."""
    risco = (
        0.08
        + 0.45 * np.clip(df["recency_days"].fillna(0) / 180, 0, 1)
        + 0.12 * np.clip(df["flight_incidents"].fillna(0), 0, 3)
        - 0.15 * np.clip(df["frequency"].fillna(0) / 24, 0, 1)
    )
    return np.clip(risco, 0.01, 0.99).round(3).to_numpy()


def predict_churn(df: pd.DataFrame) -> list[float]:
    """Score de evasão 0–1 via MLflow Serving; fallback por regras se indisponível."""
    if df.empty:
        return []
    if settings.MLFLOW_SERVING_URL:
        try:
            payload = {"dataframe_split": df[FEATURES].fillna(0).to_dict(orient="split")}
            resp = requests.post(settings.MLFLOW_SERVING_URL, json=payload, timeout=15)
            resp.raise_for_status()
            body = resp.json()
            preds = body.get("predictions", body) if isinstance(body, dict) else body
            valores = np.asarray(preds, dtype=float).reshape(len(df), -1)[:, -1]
            if valores.max() > 1:  # escala 0–1000
                valores = valores / 1000
            return np.clip(valores, 0, 1).round(3).tolist()
        except Exception:
            pass
    return _rules(df).tolist()
