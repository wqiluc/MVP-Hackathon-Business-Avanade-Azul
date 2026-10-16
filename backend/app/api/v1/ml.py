from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.schemas.ml_schema import MLTrainResponse
from app.services.ml_service import train_and_register_churn_model

router = APIRouter()

@router.post("/train", response_model=MLTrainResponse)
def train_model(current_user: dict = Depends(get_current_user)):
    """
    Executa o treinamento do modelo de Machine Learning (Churn/CLV) 
    sobre os dados da camada OURO e registra as métricas no MLflow.
    """
    try:
        result = train_and_register_churn_model()
        return MLTrainResponse(**result)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Falha ao executar o treinamento no MLflow: {str(e)}"
        )