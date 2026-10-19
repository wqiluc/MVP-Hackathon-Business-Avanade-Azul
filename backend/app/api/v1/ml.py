from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, require_admin
from app.services.schemas.ml_schema import MLTrainResponse
from app.services.ml_service import get_active_model_info, train_and_register_churn_model

router = APIRouter()

@router.get("")
@router.get("/")
def modelo_ativo(current_user: dict = Depends(get_current_user)):
    """Métricas do classificador high_risk_flag ativo no MLflow."""
    return get_active_model_info()

@router.post("/train", response_model=MLTrainResponse)
def train_model(current_user: dict = Depends(require_admin)):
    """Admin-only training for the high_risk_flag classifier in Gold."""
    try:
        return MLTrainResponse(**train_and_register_churn_model())
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
