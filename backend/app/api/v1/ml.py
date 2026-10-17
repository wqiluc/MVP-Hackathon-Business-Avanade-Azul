from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.schemas.ml_schema import MLTrainResponse
from app.services.ml_service import train_and_register_churn_model

router = APIRouter()

@router.get("")
@router.get("/")
def modelo_ativo(current_user: dict = Depends(get_current_user)):
    """Métricas do modelo de evasão ativo no MLflow (formato ModeloInfo do front)."""
    base = {"nome": "Modelo de evasão (RandomForest)", "plataforma": "MLflow", "metaAcuracia": 0.9}
    try:
        import mlflow
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

@router.post("/train", response_model=MLTrainResponse)
def train_model(current_user: dict = Depends(get_current_user)):
    """Treina o modelo sobre a camada OURO e registra métricas no MLflow."""
    try:
        return MLTrainResponse(**train_and_register_churn_model())
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Falha ao executar o treinamento no MLflow: {str(e)}")
