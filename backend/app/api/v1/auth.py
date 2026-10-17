from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.schemas.auth_schema import LoginRequest, SessaoResponse, Usuario
from app.core.security import create_jwt_token

router = APIRouter()

@router.post("/login", response_model=SessaoResponse)
def login(req: LoginRequest):
    """Autentica a equipe interna da Azul e emite o JWT (formato Sessao do front)."""
    legado = req.username == "analista_azul" and req.password == "azul123"
    atual = (req.email or "").strip().lower() == settings.DEMO_EMAIL.lower() and req.senha == settings.DEMO_PASSWORD
    if not (legado or atual):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas. Verifique usuário e senha.",
        )

    login_id = settings.DEMO_EMAIL if atual else "analista_azul"
    token = create_jwt_token({"sub": login_id, "role": "ANALYST"})
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    return SessaoResponse(
        access_token=token, token_type="bearer", role="ANALYST", token=token,
        usuario=Usuario(id="u-analista", nome="Ana Analista", email=settings.DEMO_EMAIL,
                        perfil="analista", equipe="CRM e Relacionamento"),
        expiraEm=expira.isoformat(),
    )
