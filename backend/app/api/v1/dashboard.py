from typing import Optional
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.services.crm_service import CrmService

router = APIRouter()

@router.get("/resumo")
def resumo(persona: Optional[str] = None, tier: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Agregados da camada Gold para o Dashboard de CRM."""
    return CrmService.resumo_dashboard(persona, tier)
