from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(..., example="analista_azul", description="Nome de usuário corporativo da Azul")
    password: str = Field(..., example="azul123", description="Senha de acesso ao painel")

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer Token gerado para autenticação")
    token_type: str = Field(default="bearer", description="Tipo do token (Bearer)")
    role: str = Field(default="ANALYST", description="Papel/Role do usuário no sistema Azul")