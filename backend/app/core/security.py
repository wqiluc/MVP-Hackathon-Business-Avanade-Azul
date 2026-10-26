import hashlib
import hmac
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer()


def _is_example_secret(value: str) -> bool:
    normalized = value.lower()
    return any(
        marker in normalized
        for marker in (
            "replace", "change-me", "changeme", "default", "example",
            "your-secret", "your-password", "password", "admin-pass",
            "development", "sua_chave", "0123456789", "abcdefghijklmnopqrstuvwxyz",
            "qwerty", "jwt-secret", "jwt_secret", "secret-key", "secret_key",
        )
    )


def validate_production_auth_settings() -> None:
    secret = settings.JWT_SECRET_KEY
    counts = Counter(secret)
    # Reject low-diversity strings; this is a guard, not proof of random generation.
    estimated_bits = sum(
        -count * math.log2(count / len(secret)) for count in counts.values()
    )
    if (
        not settings.JWT_SECRET_CONFIGURED
        or len(secret) < 32
        or len(counts) < 16
        or estimated_bits < 128
        or _is_example_secret(secret)
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY deve ser configurada com pelo menos 32 caracteres "
            "aleatórios, sem valores de exemplo."
        )
    email = settings.ADMIN_EMAIL.strip()
    password = settings.ADMIN_PASSWORD
    if (
        email.count("@") != 1
        or any(char.isspace() for char in email)
        or not all(email.split("@", 1))
        or email.lower().endswith(".invalid")
        or len(password) < 16
        or len(set(password)) < 8
        or _is_example_secret(password)
    ):
        raise RuntimeError(
            "Configure ADMIN_EMAIL e ADMIN_PASSWORD em produção; a senha deve "
            "ter pelo menos 16 caracteres, sem valores de exemplo."
        )
    if settings.DEMO_EMAIL or settings.DEMO_PASSWORD:
        raise RuntimeError("Contas DEMO não são permitidas em produção.")

def anonymize_identifier(raw_id: str) -> str:
    """Create a keyed pseudonym; this does not anonymize the underlying identity."""
    message = (
        # Persisted pseudonyms depend on this legacy domain; changing it needs migration.
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
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        if not isinstance(payload["sub"], str) or not payload["sub"].strip():
            raise jwt.InvalidTokenError("Missing subject")
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
