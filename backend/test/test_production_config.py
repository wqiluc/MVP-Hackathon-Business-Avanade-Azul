import pytest

from app.config import settings
from run import validate_runtime_settings

SECRET = "s3cr3t-value-do-not-leak"
VALID = {
    "ENVIRONMENT": "production",
    "JWT_SECRET_KEY": "x" * 40,
    "JWT_SECRET_CONFIGURED": True,
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": "admin-pass",
    "CORS_ORIGINS": "https://app.example.com",
    "LLM_PROVIDER": "disabled",
    "DATA_LAKE_BACKEND": "snowflake",
    "SNOWFLAKE_ACCOUNT": "acct",
    "SNOWFLAKE_USER": "user",
    "SNOWFLAKE_PASSWORD": SECRET,
    "SNOWFLAKE_DATABASE": "AZUL_DATA_LAKE",
    "SNOWFLAKE_WAREHOUSE": "WH",
    "MLFLOW_TRACKING_URI": "https://mlflow.example.com",
    "MLFLOW_SERVING_URL": "https://serving.example.com/invocations",
    "MLFLOW_LOCAL_INFERENCE": False,
    "AI_RATE_LIMIT_ENABLED": True,
    "REDIS_URL": "redis://redis.example.invalid:6379/0",
}


@pytest.fixture
def prod(monkeypatch):
    def apply(**overrides):
        for key, value in {**VALID, **overrides}.items():
            monkeypatch.setattr(settings, key, value)
    return apply


def test_valid_production_config_is_accepted(prod):
    prod()
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
        {"ADMIN_PASSWORD": ""},
    ],
)
def test_invalid_production_config_is_rejected_without_secrets(prod, override):
    prod(**override)
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_settings()
    assert SECRET not in str(exc.value)
    assert "x" * 40 not in str(exc.value)


def test_development_defaults_unchanged(prod):
    prod(ENVIRONMENT="development", DATA_LAKE_BACKEND="duckdb",
         MLFLOW_TRACKING_URI="http://localhost:5000", MLFLOW_SERVING_URL="",
         MLFLOW_LOCAL_INFERENCE=True, SNOWFLAKE_ACCOUNT="")
    validate_runtime_settings()


@pytest.mark.parametrize("provider", ["openai", "disabled"])
def test_supported_llm_providers_are_accepted(prod, provider):
    prod(ENVIRONMENT="development", LLM_PROVIDER=provider)
    validate_runtime_settings()


@pytest.mark.parametrize("provider", ["ollama", "unknown"])
def test_unsupported_llm_provider_is_rejected(prod, provider):
    prod(ENVIRONMENT="development", LLM_PROVIDER=provider)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER deve ser 'openai' ou 'disabled'"):
        validate_runtime_settings()


def test_disabled_llm_provider_allows_application_startup(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:5173")

    validate_runtime_settings()
