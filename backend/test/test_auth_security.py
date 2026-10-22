import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_jwt_token
from run import app


@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
    monkeypatch.setattr(settings, "DEMO_EMAIL", "analyst@example.test")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", secrets.token_urlsafe(24))
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", secrets.token_urlsafe(24))
    return TestClient(app)


def test_configured_demo_can_login_in_development(auth):
    response = auth.post("/api/v1/auth/login", json={
        "email": settings.DEMO_EMAIL, "senha": settings.DEMO_PASSWORD,
    })
    assert response.status_code == 200
    assert response.json()["role"] == "ANALYST"


def test_demo_is_rejected_in_production_even_if_configured(auth, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", " Production ")
    response = auth.post("/api/v1/auth/login", json={
        "email": settings.DEMO_EMAIL, "senha": settings.DEMO_PASSWORD,
    })
    assert response.status_code == 401


def test_configured_admin_can_login_in_production(auth, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = auth.post("/api/v1/auth/login", json={
        "email": settings.ADMIN_EMAIL, "senha": settings.ADMIN_PASSWORD,
    })
    assert response.status_code == 200
    claims = jwt.decode(
        response.json()["token"], settings.JWT_SECRET_KEY, algorithms=["HS256"]
    )
    assert claims["sub"] == settings.ADMIN_EMAIL
    assert claims["role"] == "ADMIN"


def test_invalid_credentials_do_not_expose_password(auth):
    response = auth.post("/api/v1/auth/login", json={
        "email": settings.ADMIN_EMAIL, "senha": "invalid",
    })
    assert response.status_code == 401
    assert settings.ADMIN_PASSWORD not in response.text


@pytest.mark.parametrize("kind", ["invalid", "expired", "missing_exp", "missing_sub"])
def test_invalid_or_expired_token_is_rejected(auth, kind):
    claims = {"sub": settings.ADMIN_EMAIL, "role": "ADMIN"}
    if kind == "invalid":
        token = "not-a-jwt"
    elif kind == "expired":
        token = jwt.encode(
            claims | {"exp": datetime.now(timezone.utc) - timedelta(seconds=10)},
            settings.JWT_SECRET_KEY, algorithm="HS256",
        )
    elif kind == "missing_exp":
        token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm="HS256")
    else:
        token = create_jwt_token({"role": "ADMIN"})
    # This route validates authentication before calling its service.
    response = auth.get("/api/v1/clientes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert token not in response.text
