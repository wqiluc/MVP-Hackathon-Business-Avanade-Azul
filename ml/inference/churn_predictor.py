import numpy as np
import pandas as pd
import requests


class ChurnPredictor:
    FEATURES = ["frequency", "recency_days", "total_spend", "flight_incidents", "avg_ticket"]

    @classmethod
    def predict(
        cls,
        df: pd.DataFrame,
        mlflow_serving_url: str,
        allow_local_inference: bool = False,
    ) -> list[float]:
        """Return model scores only; the legacy local flag never fabricates scores."""
        if df.empty:
            return []
        if not mlflow_serving_url:
            raise RuntimeError(
                "MLflow Serving não está configurado. Defina MLFLOW_SERVING_URL; "
                "MLFLOW_LOCAL_INFERENCE não substitui um modelo registrado."
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
