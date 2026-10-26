from pydantic import BaseModel, Field

class ClientAnalysisRequest(BaseModel):
    raw_user_id: str = Field(..., example="12345678900", description="CPF ou ID do cliente a ser anonimizado")
    frequency: int = Field(..., ge=0, example=12)
    total_spend: float = Field(..., ge=0.0, example=45000.0)
    incidents: int = Field(..., ge=0, example=2)
    incident_type: str = Field(default="Downgrade Involuntário", example="Downgrade Involuntário")

class ClientAnalysisResponse(BaseModel):
    audience: str
    client_identifier: str
    metrics: dict
    graph_rag_context: dict
    reasoning: str
    action_proposal: dict
    audit_status: str
