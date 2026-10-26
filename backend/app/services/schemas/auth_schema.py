from typing import Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    # Contrato do front: email/senha. username/password mantidos por compatibilidade.
    email: Optional[str] = Field(default=None, example="analista@exemplo.com")
    senha: Optional[str] = Field(default=None, example="azul2026")
    username: Optional[str] = Field(default=None, example="analista_azul")
    password: Optional[str] = Field(default=None, example="azul123")

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT gerado para autenticação")
    token_type: str = Field(default="bearer", description="Tipo do token (Bearer)")
    role: str = Field(default="ANALYST", description="Papel/Role do usuário no sistema Azul")

class Usuario(BaseModel):
    id: str
    nome: str
    email: str
    perfil: str
    equipe: str

class SessaoResponse(TokenResponse):
    """Contrato do front (Sessao) + campos OAuth legados."""
    token: str
    usuario: Usuario
    expiraEm: str
