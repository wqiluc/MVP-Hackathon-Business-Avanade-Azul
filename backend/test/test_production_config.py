import secrets
import os
import subprocess
import sys

import pytest

from app.config import Settings, settings
from run import validate_runtime_settings

SECRET = "s3cr3t-value-do-not-leak"
VALID = {
    "ENVIRONMENT": "production",
    "JWT_SECRET_KEY": secrets.token_urlsafe(48),
    "JWT_SECRET_CONFIGURED": True,
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": secrets.token_urlsafe(24),
    "DEMO_EMAIL": "",
    "DEMO_PASSWORD": "",
    "CORS_ORIGINS": "https://app.example.com",
    "LLM_PROVIDER": "disabled",
    "LLM_FALLBACK_PROVIDER": "disabled",
    "DATA_LAKE_BACKEND": "snowflake",
    "SNOWFLAKE_ACCOUNT": "acct",
    "SNOWFLAKE_USER": "user",
    "SNOWFLAKE_PASSWORD": SECRET,
    "SNOWFLAKE_DATABASE": "AZUL_DATA_LAKE",
    "SNOWFLAKE_WAREHOUSE": "WH",
    "MLFLOW_TRACKING_URI": "https://mlflow.example.com",
    "MLFLOW_SERVING_URL": "https://serving.example.com/invocations",
    "MLFLOW_LOCAL_INFERENCE": False,
    "GEMINI_TIMEOUT_SECONDS": 12,
    "AI_RATE_LIMIT_ENABLED": True,
    "REDIS_URL": "redis://redis.example.invalid:6379/0",
}


@pytest.fixture
def prod(monkeypatch):
    def apply(**overrides):
        monkeypatch.setattr("ml.models.mlflow_tracker.MODEL_NAME", "crm-test-model")
        for key, value in {**VALID, **overrides}.items():
            monkeypatch.setattr(settings, key, value)
    return apply


def test_valid_production_config_is_accepted(prod):
    prod()
    validate_runtime_settings()


def test_production_requires_model_name(prod, monkeypatch):
    prod()
    monkeypatch.setattr("ml.models.mlflow_tracker.MODEL_NAME", "")
    with pytest.raises(RuntimeError, match="MLFLOW_MODEL_NAME"):
        validate_runtime_settings()


@pytest.mark.parametrize(
    "override",
    [
        {"DATA_LAKE_BACKEND": "duckdb"},
        {"SNOWFLAKE_ACCOUNT": ""},
        {"SNOWFLAKE_USER": ""},
        {"SNOWFLAKE_PASSWORD": ""},
        {"SNOWFLAKE_DATABASE": ""},
        {"SNOWFLAKE_WAREHOUSE": "  "},
        {"MLFLOW_TRACKING_URI": ""},
        {"MLFLOW_TRACKING_URI": "http://localhost:5000"},
        {"MLFLOW_TRACKING_URI": "http://127.0.0.1:5000"},
        {"MLFLOW_TRACKING_URI": "file:///tmp/mlruns"},
        {"MLFLOW_TRACKING_URI": "./mlruns"},
        {"MLFLOW_SERVING_URL": ""},
        {"MLFLOW_SERVING_URL": "not-a-url"},
        {"MLFLOW_LOCAL_INFERENCE": True},
        {"JWT_SECRET_CONFIGURED": False},
        {"JWT_SECRET_KEY": ""},
        {"JWT_SECRET_KEY": "short"},
        {"JWT_SECRET_KEY": "x" * 64},
        {"JWT_SECRET_KEY": "replace-with-a-random-secret-for-production"},
        {"JWT_SECRET_KEY": "0123456789abcdef" * 4},
        {"ADMIN_EMAIL": ""},
        {"ADMIN_EMAIL": "admin@example.invalid"},
        {"ADMIN_PASSWORD": ""},
        {"ADMIN_PASSWORD": "replace-before-use"},
        {"ADMIN_PASSWORD": "x" * 64},
        {"DEMO_EMAIL": "demo@example.test"},
        {"DEMO_PASSWORD": "demo"},
        {"CORS_ORIGINS": "*"},
        {"CORS_ORIGINS": ""},
        {"CORS_ORIGINS": "https://*.example.com"},
        {"CORS_ORIGINS": "https://user:pass@example.com"},
        {"ENVIRONMENT": "prodution"},
        {"ACCESS_TOKEN_EXPIRE_HOURS": 0},
        {"GEMINI_TIMEOUT_SECONDS": 0},
    ],
)
def test_invalid_production_config_is_rejected_without_secrets(prod, override):
    prod(**override)
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings()
    assert SECRET not in str(exc.value)
    assert VALID["JWT_SECRET_KEY"] not in str(exc.value)
    assert VALID["ADMIN_PASSWORD"] not in str(exc.value)


def test_development_defaults_unchanged(prod):
    prod(ENVIRONMENT="development", DATA_LAKE_BACKEND="duckdb",
         MLFLOW_TRACKING_URI="http://localhost:5000", MLFLOW_SERVING_URL="",
         MLFLOW_LOCAL_INFERENCE=True, SNOWFLAKE_ACCOUNT="")
    validate_runtime_settings()


@pytest.mark.parametrize("provider", ["openai", "gemini", "disabled"])
def test_supported_llm_providers_are_accepted(prod, provider):
    prod(ENVIRONMENT="development", LLM_PROVIDER=provider)
    validate_runtime_settings()


@pytest.mark.parametrize("provider", ["ollama", "unknown"])
def test_unsupported_llm_provider_is_rejected(prod, provider):
    prod(ENVIRONMENT="development", LLM_PROVIDER=provider)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER deve ser 'openai', 'gemini' ou 'disabled'"):
        validate_runtime_settings()


@pytest.mark.parametrize("provider", ["openai", "gemini", "disabled"])
def test_supported_llm_fallback_providers_are_accepted(prod, provider):
    prod(
        ENVIRONMENT="development",
        LLM_PROVIDER="gemini" if provider == "openai" else "openai",
        LLM_FALLBACK_PROVIDER=provider,
    )
    validate_runtime_settings()


def test_same_primary_and_fallback_provider_is_rejected(prod):
    prod(
        ENVIRONMENT="development",
        LLM_PROVIDER="gemini",
        LLM_FALLBACK_PROVIDER="gemini",
    )
    with pytest.raises(RuntimeError, match="não pode repetir"):
        validate_runtime_settings()


def test_unsupported_llm_fallback_provider_is_rejected(prod):
    prod(
        ENVIRONMENT="development",
        LLM_PROVIDER="openai",
        LLM_FALLBACK_PROVIDER="ollama",
    )
    with pytest.raises(RuntimeError, match="LLM_FALLBACK_PROVIDER deve ser"):
        validate_runtime_settings()


def test_disabled_provider_rejects_configured_fallback(prod):
    prod(
        ENVIRONMENT="development",
        LLM_PROVIDER="disabled",
        LLM_FALLBACK_PROVIDER="gemini",
    )
    with pytest.raises(RuntimeError, match="deve ser 'disabled'"):
        validate_runtime_settings()


def test_disabled_llm_provider_allows_application_startup(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:5173")

    validate_runtime_settings()


def test_production_does_not_load_local_dotenv_files():
    script = """
import dotenv
def forbidden(*args, **kwargs):
    raise AssertionError("Production loaded a local dotenv file")
dotenv.load_dotenv = forbidden
from app.config import settings
assert settings.is_production
"""
    subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "ENVIRONMENT": "production"},
        check=True,
        capture_output=True,
    )


def test_empty_local_key_generates_ephemeral_key_without_allowing_it_in_production():
    local = Settings(ENVIRONMENT="development", JWT_SECRET_KEY="")
    assert len(local.JWT_SECRET_KEY) >= 32
    production = Settings(ENVIRONMENT="production", JWT_SECRET_KEY="")
    assert production.JWT_SECRET_KEY == ""


def test_local_cors_default_is_not_inherited_by_production():
    local = Settings(ENVIRONMENT="development", CORS_ORIGINS="")
    assert "localhost" in local.CORS_ORIGINS
    production = Settings(ENVIRONMENT="production", CORS_ORIGINS="")
    assert production.CORS_ORIGINS == ""
