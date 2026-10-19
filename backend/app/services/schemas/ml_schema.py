from pydantic import BaseModel, Field

class MLTrainResponse(BaseModel):
    run_id: str = Field(..., example="8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c", description="ID de execução gerado no MLflow")
    accuracy: float = Field(..., example=0.9425, description="Acurácia calculada sobre o conjunto de teste (Meta >= 90%)")
    precision: float = Field(..., example=0.9210, description="Precisão do modelo")
    recall: float = Field(..., example=0.9500, description="Recall / Sensibilidade do modelo")
    status: str = Field(..., example="Modelo registrado no MLflow com sucesso")