from unittest.mock import Mock

import pytest
import requests
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
    def unexpected_check(*args, **kwargs):
        raise AssertionError("liveness must not probe dependencies")

    monkeypatch.setattr(health, "_check_duckdb", unexpected_check)
    monkeypatch.setattr(health, "_check_http_health", unexpected_check)

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
