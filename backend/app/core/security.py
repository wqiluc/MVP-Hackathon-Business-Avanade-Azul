import hashlib
import hmac
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer()

def anonymize_identifier(raw_id: str) -> str:
    """Create a keyed pseudonym; this does not anonymize the underlying identity."""
    message = (
        b"aeroshield:client-identifier:v1\0"
        + raw_id.strip().encode("utf-8")
    )
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return f"AZ-{digest[:32]}"

def create_jwt_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_bearer)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token expirado. Por favor, faça login novamente."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token de autenticação inválido."
        )


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return current_user
