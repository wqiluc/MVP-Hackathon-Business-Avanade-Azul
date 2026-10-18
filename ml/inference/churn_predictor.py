import numpy as np
import pandas as pd
import requests


class ChurnPredictor:
    FEATURES = ["frequency", "recency_days", "total_spend", "flight_incidents", "avg_ticket"]

    @staticmethod
    def _rules(df: pd.DataFrame) -> np.ndarray:
        """Probabilidade de evasão (0–1) por regras, usada sem MLflow Serving."""
        risco = (
            0.08
            + 0.45 * np.clip(df["recency_days"].fillna(0) / 180, 0, 1)
            + 0.12 * np.clip(df["flight_incidents"].fillna(0), 0, 3)
            - 0.15 * np.clip(df["frequency"].fillna(0) / 24, 0, 1)
        )
        return np.clip(risco, 0.01, 0.99).round(3).to_numpy()

    @classmethod
    def predict(
        cls,
        df: pd.DataFrame,
        mlflow_serving_url: str,
        allow_local_inference: bool = False,
    ) -> list[float]:
        """Return scores from MLflow Serving, or rules only in explicit local mode."""
        if df.empty:
            return []
        if not mlflow_serving_url:
            if allow_local_inference:
                return cls._rules(df).tolist()
            raise RuntimeError(
                "MLflow Serving não está configurado. Defina MLFLOW_SERVING_URL "
                "ou habilite explicitamente MLFLOW_LOCAL_INFERENCE para uso local."
            )

        try:
            payload = {
                "dataframe_split": df[cls.FEATURES]
                .fillna(0)
                .to_dict(orient="split")
            }
            response = requests.post(mlflow_serving_url, json=payload, timeout=15)
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Falha ao consultar MLflow Serving em {mlflow_serving_url}: {exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError("MLflow Serving retornou uma resposta JSON inválida.") from exc

        predictions = body.get("predictions") if isinstance(body, dict) else body
        if predictions is None:
            raise RuntimeError("MLflow Serving não retornou o campo 'predictions'.")
        try:
            values = np.asarray(predictions, dtype=float).reshape(len(df), -1)[:, -1]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "MLflow Serving retornou previsões incompatíveis com as linhas enviadas."
            ) from exc
        if values.size != len(df) or not np.isfinite(values).all():
            raise RuntimeError(
                "MLflow Serving retornou previsões inválidas ou em quantidade incorreta."
            )
        if values.max() > 1:  # Compatibilidade com respostas percentuais legadas.
            values = values / 1000
        return np.clip(values, 0, 1).round(3).tolist()
