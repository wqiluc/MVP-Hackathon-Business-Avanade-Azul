from datetime import datetime

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from app.services.datalake_service import DataLakeService


def get_active_model_info() -> dict:
    """Retorna as informações do último modelo registrado, com o fallback atual."""
    base = {"nome": "Modelo de evasão (RandomForest)", "plataforma": "MLflow", "metaAcuracia": 0.9}
    try:
        runs = mlflow.search_runs(experiment_names=["Azul_CRM_Churn_Prediction"],
                                  order_by=["attributes.start_time DESC"], max_results=1)
        if runs.empty:
            raise LookupError
        r = runs.iloc[0]
        return base | {
            "versao": str(r["run_id"])[:8], "status": "em-producao",
            "acuracia": float(r["metrics.accuracy"]), "auc": None,
            "treinadoEm": r["start_time"].isoformat() if isinstance(r["start_time"], datetime) else None,
        }
    except Exception:
        return base | {"versao": "—", "status": "aguardando-registro", "acuracia": None, "auc": None, "treinadoEm": None}


def train_and_register_churn_model() -> dict:
    """
    Treina o modelo de Machine Learning (RandomForest) utilizando as features da 
    camada OURO do Data Lake e registra parâmetros, métricas e o modelo no MLflow.
    """
    mlflow.set_experiment("Azul_CRM_Churn_Prediction")
    
    df = DataLakeService.read_gold()

    if df.empty:
        raise ValueError("A camada Ouro do Data Lake está vazia. Execute o upload de dados (/data/ingest) antes de treinar o modelo.")

    if len(df) < 5:
        raise ValueError("Quantidade insuficiente de registros na camada Ouro para treinar o modelo (mínimo de 5 registros).")

    # Matriz de Atributos (X) e Alvo de Churn/Risco (y)
    X = df[['frequency', 'recency_days', 'total_spend', 'flight_incidents', 'avg_ticket']].fillna(0)
    y = df['high_risk_flag']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    with mlflow.start_run() as run:
        params = {"n_estimators": 100, "max_depth": 8, "random_state": 42}
        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        # Avaliação de Desempenho
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)

        # Log no MLflow
        mlflow.log_params(params)
        mlflow.log_metric("accuracy", float(acc))
        mlflow.log_metric("precision", float(prec))
        mlflow.log_metric("recall", float(rec))
        mlflow.sklearn.log_model(model, "churn_rf_model")

        return {
            "run_id": run.info.run_id,
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "status": "Modelo registrado no MLflow com sucesso"
        }
