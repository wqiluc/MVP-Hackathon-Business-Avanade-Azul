from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.schemas.ml_schema import MLTrainResponse
from app.services.ml_service import get_active_model_info, train_and_register_churn_model

router = APIRouter()

@router.get("")
@router.get("/")
def modelo_ativo(current_user: dict = Depends(get_current_user)):
    """Métricas do modelo de evasão ativo no MLflow (formato ModeloInfo do front)."""
    return get_active_model_info()

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
