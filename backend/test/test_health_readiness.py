from unittest.mock import Mock

import pytest
import requests
from redis.exceptions import ConnectionError as RedisConnectionError
from fastapi.testclient import TestClient

from app.api.v1 import health
from app.config import settings
from run import app


client = TestClient(app)


@pytest.fixture
def local_readiness(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)

    monkeypatch.setattr(health, "_check_duckdb", lambda: "ready")
    monkeypatch.setattr(health, "_check_http_health", lambda uri, endpoint: "ready")


def test_readiness_returns_ready_when_required_dependencies_are_healthy(
    local_readiness,
):
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"] == {
        "data_lake": "ready",
        "mlflow_tracking": "ready",
        "mlflow_serving": "not_configured",
    }


def test_local_readiness_without_mlflow_does_not_probe_external_services(
    local_readiness, monkeypatch
):
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    probe = Mock(side_effect=AssertionError("External health must not be probed"))
    monkeypatch.setattr(health, "_check_http_health", probe)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["mlflow_tracking_configured"] is False
    assert response.json()["dependencies"]["mlflow_tracking"] == "not_configured"
    probe.assert_not_called()


@pytest.mark.parametrize(
    "dependency",
    [
        "data_lake",
        "mlflow_tracking",
    ],
)
def test_readiness_fails_when_a_required_dependency_is_unavailable(
    local_readiness, monkeypatch, dependency
):
    if dependency == "data_lake":
        monkeypatch.setattr(health, "_check_duckdb", lambda: "failed")
    else:
        monkeypatch.setattr(
            health, "_check_http_health", lambda uri, endpoint: "failed"
        )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"][dependency] == "failed"


def test_readiness_fails_if_tracking_cannot_be_safely_verified(
    local_readiness, monkeypatch
):
    monkeypatch.setattr(
        settings, "MLFLOW_TRACKING_URI", "file:///workspace/mlruns"
    )
    monkeypatch.setattr(
        health, "_check_http_health", lambda uri, endpoint: "unverified"
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"]["mlflow_tracking"] == "unverified"


def test_configured_serving_is_checked_at_its_supported_ping_endpoint(
    local_readiness, monkeypatch
):
    calls = []

    def check(uri, endpoint):
        calls.append((uri, endpoint))
        return "failed" if endpoint == "ping" else "ready"

    monkeypatch.setattr(
        settings, "MLFLOW_SERVING_URL", "https://serving.test/invocations"
    )
    monkeypatch.setattr(health, "_check_http_health", check)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert calls == [
        ("http://mlflow.test", "health"),
        ("https://serving.test/invocations", "ping"),
    ]
    assert (
        response.json()["detail"]["dependencies"]["mlflow_serving"] == "failed"
    )


def test_http_dependency_check_uses_a_bounded_request(monkeypatch):
    response = Mock(status_code=200)
    request = Mock(return_value=response)
    monkeypatch.setattr(health.requests, "get", request)

    assert health._check_http_health("https://mlflow.test", "health") == "ready"
    request.assert_called_once_with(
        "https://mlflow.test/health",
        timeout=health._DEPENDENCY_TIMEOUT_SECONDS,
        allow_redirects=False,
    )


def test_duckdb_health_check_opens_and_queries_configured_database(monkeypatch):
    monkeypatch.setattr(settings, "DUCKDB_PATH", ":memory:")

    assert health._check_duckdb() == "ready"


def test_http_dependency_check_reports_unverified_for_non_http_uri():
    assert (
        health._check_http_health("file:///workspace/mlruns", "health")
        == "unverified"
    )


def test_serving_health_check_does_not_guess_an_undocumented_endpoint():
    assert (
        health._check_http_health("https://serving.test/custom", "ping")
        == "unverified"
    )


def test_liveness_does_not_check_external_dependencies(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    def unexpected_check(*args, **kwargs):
        raise AssertionError("liveness must not probe dependencies")

    monkeypatch.setattr(health, "_check_duckdb", unexpected_check)
    monkeypatch.setattr(health, "_check_http_health", unexpected_check)
    monkeypatch.setattr(health, "_check_redis", unexpected_check)

    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_snowflake_check_uses_bounded_safe_query(monkeypatch):
    cursor = Mock()
    cursor.execute.return_value = cursor
    cursor.fetchone.return_value = (1,)
    connection = Mock()
    connection.cursor.return_value = cursor
    get_connection = Mock(return_value=connection)
    monkeypatch.setattr(
        "app.services.snowflake_service.SnowflakeDataLake.get_connection",
        get_connection,
    )

    assert health._check_snowflake() == "ready"
    get_connection.assert_called_once_with(
        login_timeout=health._DEPENDENCY_TIMEOUT_SECONDS,
        network_timeout=health._DEPENDENCY_TIMEOUT_SECONDS,
        statement_timeout=health._DEPENDENCY_TIMEOUT_SECONDS,
    )
    cursor.execute.assert_called_once_with(
        "SELECT 1", timeout=health._DEPENDENCY_TIMEOUT_SECONDS
    )
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_http_request_failure_does_not_expose_exception(monkeypatch):
    secret_error = "secret endpoint credential"
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(health, "_check_duckdb", lambda: "ready")
    monkeypatch.setattr(
        health.requests,
        "get",
        Mock(side_effect=requests.ConnectionError(secret_error)),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert secret_error not in response.text


@pytest.mark.parametrize("redis_status,expected", [("ready", 200), ("failed", 503)])
def test_production_readiness_requires_redis(
    local_readiness, monkeypatch, redis_status, expected
):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis.test:6379/0")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "https://serving.test/invocations")
    monkeypatch.setattr(health, "_check_redis", lambda: redis_status)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == expected
    payload = response.json()
    dependencies = payload.get("dependencies", payload.get("detail", {}).get("dependencies"))
    assert dependencies["redis"] == redis_status


def test_disabled_rate_limit_does_not_probe_redis(local_readiness, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "https://serving.test/invocations")
    probe = Mock(side_effect=AssertionError("Redis must not be probed"))
    monkeypatch.setattr(health, "_check_redis", probe)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    probe.assert_not_called()


@pytest.mark.parametrize("available", [True, False])
def test_redis_probe_uses_existing_bounded_client(monkeypatch, available):
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://redis.test:6379/0")
    store = Mock()
    store.ping.return_value = True
    if not available:
        store.ping.side_effect = RedisConnectionError("sensitive connection details")
    factory = Mock(return_value=store)
    monkeypatch.setattr(health, "redis_client", factory)
    assert health._check_redis() == ("ready" if available else "failed")
    factory.assert_called_once_with(settings.REDIS_URL)


def test_missing_required_redis_fails_probe(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "")
    assert health._check_redis() == "failed"


def test_missing_production_redis_fails_readiness(local_readiness, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "https://serving.test/invocations")
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"]["redis"] == "failed"


def test_duckdb_readiness_does_not_probe_snowflake_or_optional_ai(local_readiness, monkeypatch):
    probe = Mock(side_effect=AssertionError("optional dependency must not be probed"))
    monkeypatch.setattr(health, "_check_snowflake", probe)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    assert client.get("/api/v1/health/ready").status_code == 200
    probe.assert_not_called()


def test_readiness_requires_selected_snowflake_backend(local_readiness, monkeypatch):
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "snowflake")
    monkeypatch.setattr(settings, "SNOWFLAKE_ACCOUNT", "")
    monkeypatch.setattr(health, "_check_duckdb", Mock(side_effect=AssertionError("wrong backend")))
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"]["data_lake"] == "failed"
