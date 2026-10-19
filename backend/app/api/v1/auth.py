from fastapi import APIRouter, HTTPException, status

from app.services.schemas.auth_schema import LoginRequest, SessaoResponse
from app.services.auth_service import AuthService, InvalidCredentialsError

router = APIRouter()

@router.post("/login", response_model=SessaoResponse)
def login(req: LoginRequest):
    """Autentica a equipe interna e retorna a sessão do frontend."""
    try:
        return AuthService.login(req)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
