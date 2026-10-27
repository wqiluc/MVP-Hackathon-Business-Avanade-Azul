from typing import List
from pydantic import BaseModel, Field

class IngestionDetails(BaseModel):
    status: str = Field(..., example="success", description="Status do processamento da ingestão")
    processed_rows: int = Field(..., example=150, description="Quantidade de linhas ingeridas e tratadas")
    ingestion_contract: str | None = Field(
        None, example="CRM_CANONICAL", description="Contrato de ingestão detectado no arquivo"
    )
    scoring_summary: dict | None = Field(None, description="Resumo agregado do scoring ML_FEATURES_52")
    layers: List[str] = Field(
        ..., 
        example=["bronze.raw_clients", "silver.cleaned_clients", "gold.client_features"],
        description="Camadas da Arquitetura Medalhão atualizadas"
    )

class UploadResponse(BaseModel):
    message: str = Field(..., example="Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!")
    details: IngestionDetails
