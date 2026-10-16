from fastapi import APIRouter, HTTPException, status
from app.schemas.auth_schema import LoginRequest, TokenResponse
from app.core.security import create_jwt_token

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """
    Realiza a autenticação de usuários da equipe interna da Azul e emite o token JWT.
    """
    # Credenciais padrões para ambiente de desenvolvimento/avaliação do Hackathon
    if req.username == "analista_azul" and req.password == "azul123":
        token_data = {"sub": req.username, "role": "ANALYST"}
        jwt_token = create_jwt_token(token_data)
        
        return TokenResponse(
            access_token=jwt_token,
            token_type="bearer",
            role="ANALYST"
        )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas. Verifique usuário e senha."
    )
