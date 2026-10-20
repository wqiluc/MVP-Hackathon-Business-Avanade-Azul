"""Opt-in smoke tests against the disposable local Redis server, never fakeredis."""

import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.core import ai_rate_limit
from app.core.security import create_jwt_token
from app.services.crm_service import CrmService
from run import app


@pytest.fixture
def real_redis(monkeypatch):
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_IP_REQUESTS", 5)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", secrets.token_urlsafe(32))
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    ai_rate_limit.redis_client.cache_clear()
    store = ai_rate_limit.redis_client(settings.REDIS_URL)
    assert store.connection_pool.connection_kwargs["host"] == "127.0.0.1"
    assert store.connection_pool.connection_kwargs["port"] == 6379
    try:
        yield store
    finally:
        store.close()
        ai_rate_limit.redis_client.cache_clear()


def auth(user):
    return {"Authorization": "Bearer " + create_jwt_token({"sub": user})}


@pytest.mark.skipif(
    os.getenv("CRM_REAL_REDIS_SMOKE") != "available",
    reason="Requires disposable Redis 7 on localhost:6379 and a real 60-second wait.",
)
def test_real_redis_admission_expiry_and_atomic_counters(real_redis, monkeypatch):
    assert real_redis.ping() is True
    assert real_redis.info("server")["redis_version"].startswith("7.")
    lookup = Mock(return_value={
        "id": "AZ-real-smoke", "tier": "Safira", "voos12m": 10, "receita12m": 5000,
        "_churn_score": None, "_flight_incidents": 0, "_incident_type": None,
        "proximaAcao": {"origem": "regras"},
    })
    provider = Mock(side_effect=AssertionError("No external OpenAI call is allowed"))
    monkeypatch.setattr(CrmService, "obter", lookup)
    monkeypatch.setattr("openai.OpenAI", provider)
    path = "/api/v1/clientes/AZ-real-smoke/recomendacao"
    user_key = ai_rate_limit._key("user", "real-smoke-one")
    ip_key = ai_rate_limit._key("ip", "testclient")

    with TestClient(app) as client:
        response = client.post(path, headers=auth("real-smoke-one"))
        assert response.status_code == 200
        assert response.json()["origem"] == "regras"
        assert real_redis.get(user_key) == b"1"
        assert real_redis.get(ip_key) == b"1"
        initial_ttl = real_redis.pttl(user_key)
        assert 59000 <= initial_ttl <= 60000
        assert client.post(path, headers=auth("real-smoke-one")).status_code == 200
        assert real_redis.get(user_key) == b"2"
        assert real_redis.get(ip_key) == b"2"

        lookup.reset_mock()
        blocked = client.post(
            "/api/v1/ai/AZ-real-smoke/recomendacao", headers=auth("real-smoke-one")
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"] == "AI_RATE_LIMIT_EXCEEDED"
        assert 1 <= int(blocked.headers["Retry-After"]) <= 60
        assert 0 < real_redis.pttl(user_key) <= initial_ttl
        assert real_redis.get(user_key) == b"2"
        assert real_redis.get(ip_key) == b"2"
        lookup.assert_not_called()
        provider.assert_not_called()

        for user in ["real-smoke-two", "real-smoke-two", "real-smoke-three"]:
            assert client.post(path, headers=auth(user)).status_code == 200
        assert real_redis.get(ip_key) == b"5"
        lookup.reset_mock()
        blocked_ip = client.post(path, headers=auth("real-smoke-four"))
        assert blocked_ip.status_code == 429
        assert 1 <= int(blocked_ip.headers["Retry-After"]) <= 60
        assert real_redis.get(ip_key) == b"5"
        assert real_redis.get(ai_rate_limit._key("user", "real-smoke-four")) is None
        lookup.assert_not_called()
        provider.assert_not_called()

        concurrent_keys = [
            ai_rate_limit._key("user", "real-concurrent"),
            ai_rate_limit._key("ip", "real-concurrent"),
        ]

        def consume(_):
            return real_redis.eval(
                ai_rate_limit._CONSUME_SCRIPT, 2, *concurrent_keys, 60000, 2, 5
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume, range(20)))
        assert results.count(0) == 2
        assert all(real_redis.get(key) == b"2" for key in concurrent_keys)

        time.sleep(max(real_redis.pttl(user_key), real_redis.pttl(ip_key)) / 1000 + 0.2)
        assert real_redis.get(user_key) is None
        assert real_redis.get(ip_key) is None
        resumed = client.post(path, headers=auth("real-smoke-one"))
        assert resumed.status_code == 200
        assert real_redis.get(user_key) == b"1"
        assert real_redis.get(ip_key) == b"1"
        provider.assert_not_called()
    assert not ai_rate_limit.memory_limiter._entries


@pytest.mark.skipif(
    os.getenv("CRM_REAL_REDIS_SMOKE") != "unavailable",
    reason="Requires the disposable Redis container to be stopped first.",
)
def test_real_redis_stopped_fails_closed_in_production(real_redis, monkeypatch):
    with pytest.raises(RedisConnectionError):
        real_redis.ping()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    lookup = Mock(side_effect=AssertionError("Blocked request reached CRM"))
    provider = Mock(side_effect=AssertionError("Blocked request reached OpenAI"))
    memory = Mock(side_effect=AssertionError("Production fell back to memory"))
    monkeypatch.setattr(CrmService, "obter", lookup)
    monkeypatch.setattr("openai.OpenAI", provider)
    monkeypatch.setattr(ai_rate_limit.memory_limiter, "consume", memory)
    # Isolate request-time production admission from unrelated Snowflake/MLflow startup.
    response = TestClient(app).post(
        "/api/v1/clientes/AZ-real-smoke/recomendacao", headers=auth("real-smoke-outage")
    )
    assert response.status_code == 503
    assert response.json()["error"] == "AI_RATE_LIMIT_UNAVAILABLE"
    lookup.assert_not_called()
    provider.assert_not_called()
    memory.assert_not_called()
    assert not ai_rate_limit.memory_limiter._entries
