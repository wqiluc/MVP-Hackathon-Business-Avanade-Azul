from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.requests import Request

from app.config import settings
from app.core import ai_rate_limit
from app.core.security import create_jwt_token
from app.services.crm_service import CrmService
from run import app, validate_runtime_settings


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_IP_REQUESTS", 10)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "rate-limit-tests-not-production-secret")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    client = {
        "id": "AZ-test", "tier": "Safira", "voos12m": 10, "receita12m": 5000,
        "_churn_score": None, "_flight_incidents": 0, "_incident_type": None,
        "proximaAcao": {"origem": "regras"},
    }
    monkeypatch.setattr(CrmService, "obter", lambda _id: client)
    monkeypatch.setattr(CrmService, "listar", lambda *_args: [])
    return TestClient(app)


def headers(user="one"):
    return {"Authorization": f"Bearer {create_jwt_token({'sub': user})}"}


def request(ip="192.0.2.1", forwarded=None):
    return Request({
        "type": "http", "client": (ip, 1234) if ip else None,
        "headers": [(b"x-forwarded-for", forwarded.encode())] if forwarded else [],
    })


def test_first_request_and_rules_fallback_continue_working(limited):
    result = limited.post("/api/v1/clientes/AZ-test/recomendacao", headers=headers())
    assert result.status_code == 200
    assert result.json()["origem"] == "regras"
    assert limited.get("/api/v1/clientes", headers=headers()).status_code == 200


def test_limit_429_retry_after_and_alias_share_budget(limited, monkeypatch):
    path = "/api/v1/clientes/AZ-test/recomendacao"
    assert limited.post(path, headers=headers()).status_code == 200
    assert limited.post(path, headers=headers()).status_code == 200
    blocked_work = Mock(side_effect=AssertionError("Must not reach CRM or OpenAI"))
    monkeypatch.setattr(CrmService, "obter", blocked_work)
    response = limited.post("/api/v1/ai/AZ-test/recomendacao", headers=headers())
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.json()["success"] is False
    assert response.json()["error"] == "AI_RATE_LIMIT_EXCEEDED"
    assert response.json()["message"] == "Muitas solicitações de IA. Tente novamente em instantes."
    blocked_work.assert_not_called()
    assert limited.get("/api/v1/clientes", headers=headers()).status_code == 200


def test_counter_resets_and_retry_after_decreases(limited, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(ai_rate_limit.time, "monotonic", lambda: clock[0])
    path = "/api/v1/clientes/AZ-test/recomendacao"
    for _ in range(2):
        assert limited.post(path, headers=headers()).status_code == 200
    clock[0] = 40.1
    assert limited.post(path, headers=headers()).headers["Retry-After"] == "30"
    clock[0] = 70
    assert limited.post(path, headers=headers()).status_code == 200


def test_users_at_same_ip_have_separate_user_budgets(limited):
    path = "/api/v1/clientes/AZ-test/recomendacao"
    for _ in range(2):
        assert limited.post(path, headers=headers("one")).status_code == 200
    assert limited.post(path, headers=headers("one")).status_code == 429
    assert limited.post(path, headers=headers("two")).status_code == 200


def test_user_cannot_bypass_limit_by_changing_ip(limited):
    for ip in ["192.0.2.1", "192.0.2.2"]:
        ai_rate_limit.enforce_ai_rate_limit(request(ip), {"sub": "same-user"})
    third_request = request("192.0.2.3")
    with pytest.raises(HTTPException) as error:
        ai_rate_limit.enforce_ai_rate_limit(third_request, {"sub": "same-user"})
    assert error.value.status_code == 429


def test_ip_second_barrier_covers_multiple_users(limited, monkeypatch):
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_IP_REQUESTS", 2)
    for user in ["one", "two"]:
        ai_rate_limit.enforce_ai_rate_limit(request(), {"sub": user})
    third_request = request()
    with pytest.raises(HTTPException) as error:
        ai_rate_limit.enforce_ai_rate_limit(third_request, {"sub": "three"})
    assert error.value.status_code == 429


def test_ip_fallback_and_forwarded_headers_cannot_bypass(limited):
    for _ in range(2):
        ai_rate_limit.enforce_ai_rate_limit(request(), {})
    spoofed_request = request(forwarded="203.0.113.9")
    with pytest.raises(HTTPException) as error:
        ai_rate_limit.enforce_ai_rate_limit(spoofed_request, {})
    assert error.value.status_code == 429
    ai_rate_limit.enforce_ai_rate_limit(request("192.0.2.2"), {})


def test_disabled_and_unauthenticated_requests(limited, monkeypatch):
    path = "/api/v1/clientes/AZ-test/recomendacao"
    assert limited.post(path).status_code in {401, 403}
    assert ai_rate_limit.memory_limiter._entries == {}
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", False)
    for _ in range(4):
        assert limited.post(path, headers=headers()).status_code == 200
    assert ai_rate_limit.memory_limiter._entries == {}


def test_missing_both_identities_is_rejected(limited):
    anonymous_request = request(None)
    with pytest.raises(HTTPException) as error:
        ai_rate_limit.enforce_ai_rate_limit(anonymous_request, {})
    assert error.value.status_code == 503


def test_memory_consumption_is_atomic_and_prunes_expired_entries(monkeypatch):
    limiter = ai_rate_limit.MemoryRateLimiter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: limiter.consume({"one": 10}, 60), range(100)))
    assert results.count(0) == 10
    monkeypatch.setattr(ai_rate_limit.time, "monotonic", lambda: float("inf"))
    assert limiter.consume({"new": 1}, 60) == 0
    assert "one" not in limiter._entries


def test_redis_lua_atomic_budgets_ttl_and_expiry():
    redis = fakeredis.FakeRedis()
    keys = ["crm:{ai-rate-limit}:user:test", "crm:{ai-rate-limit}:ip:test"]
    arguments = [ai_rate_limit._CONSUME_SCRIPT, 2, *keys, 60000, 2, 5]
    assert redis.eval(*arguments) == 0
    assert redis.eval(*arguments) == 0
    assert 1 <= redis.eval(*arguments) <= 60000
    assert redis.get(keys[1]) == b"2"
    assert redis.pttl(keys[0]) > 0
    redis.pexpire(keys[0], 0)
    redis.pexpire(keys[1], 0)
    assert redis.eval(*arguments) == 0


def test_redis_shared_across_workers_and_failure_closed(limited, monkeypatch):
    store = fakeredis.FakeRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setattr(ai_rate_limit, "redis_client", lambda _url: store)
    path = "/api/v1/clientes/AZ-test/recomendacao"
    for _ in range(2):
        assert limited.post(path, headers=headers()).status_code == 200
    monkeypatch.setattr(ai_rate_limit, "memory_limiter", ai_rate_limit.MemoryRateLimiter())
    assert TestClient(app).post(path, headers=headers()).status_code == 429
    monkeypatch.setattr(ai_rate_limit, "redis_client", Mock(side_effect=RedisConnectionError("secret")))
    response = limited.post(path, headers=headers("new"))
    assert response.status_code == 503
    assert response.json()["error"] == "AI_RATE_LIMIT_UNAVAILABLE"
    assert "secret" not in response.text
    assert not ai_rate_limit.memory_limiter._entries


def test_redis_atomic_under_concurrent_requests():
    store = fakeredis.FakeRedis()

    def consume(_):
        return store.eval(ai_rate_limit._CONSUME_SCRIPT, 2, "user", "ip", 60000, 10, 100)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(consume, range(50)))
    assert results.count(0) == 10
    assert store.get("user") == b"10"
    assert store.get("ip") == b"10"


def test_redis_uses_hashed_keys_and_rejects_counters_without_expiry(limited, monkeypatch):
    store = fakeredis.FakeRedis()
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost")
    monkeypatch.setattr(ai_rate_limit, "redis_client", lambda _url: store)
    ai_rate_limit.enforce_ai_rate_limit(request(), {"sub": "private@example.test"})
    keys = store.keys()
    assert len(keys) == 2
    assert all(b"private" not in key and b"192.0.2.1" not in key for key in keys)
    for key in keys:
        store.set(key, 100)
    repeated_request = request()
    with pytest.raises(HTTPException) as error:
        ai_rate_limit.enforce_ai_rate_limit(repeated_request, {"sub": "private@example.test"})
    assert error.value.status_code == 503


def test_analysis_and_recommendation_share_budget(limited):
    for _ in range(2):
        assert limited.post("/api/v1/clientes/AZ-test/recomendacao", headers=headers()).status_code == 200
    result = limited.post("/api/v1/ai/analyze", headers=headers(), json={
        "raw_user_id": "test", "frequency": 1, "total_spend": 10,
        "incidents": 0, "incident_type": "",
    })
    assert result.status_code == 429


def test_retry_after_is_exposed_through_cors(limited):
    path = "/api/v1/clientes/AZ-test/recomendacao"
    for _ in range(2):
        limited.post(path, headers=headers())
    response = limited.post(path, headers=headers() | {"Origin": "http://localhost:5173"})
    assert response.status_code == 429
    assert response.headers["access-control-expose-headers"] == "Retry-After"


def test_production_never_uses_memory(limited, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_runtime_settings()
    result = limited.post("/api/v1/clientes/AZ-test/recomendacao", headers=headers())
    assert result.status_code == 503
    assert not ai_rate_limit.memory_limiter._entries


@pytest.mark.parametrize("name,value", [
    ("AI_RATE_LIMIT_REQUESTS", 0), ("AI_RATE_LIMIT_IP_REQUESTS", -1),
    ("AI_RATE_LIMIT_WINDOW_SECONDS", 0), ("AI_OPENAI_MAX_RETRIES", -1),
    ("AI_OPENAI_MAX_RETRIES", 3), ("REDIS_URL", "https://not-redis.example"),
    ("REDIS_URL", "redis://localhost:invalid"),
    ("REDIS_URL", "redis://[invalid"),
])
def test_invalid_config_fails_startup(limited, monkeypatch, name, value):
    monkeypatch.setattr(settings, name, value)
    with pytest.raises(RuntimeError):
        validate_runtime_settings()


@pytest.mark.parametrize("reason", ["temporary", "quota"])
def test_endpoint_openai_rate_limit_fallback_and_call_cap(limited, monkeypatch, reason):
    import httpx
    import openai

    calls = []
    sleeps = []

    def parse(**_kwargs):
        calls.append(None)
        response = httpx.Response(
            429, headers={"retry-after": "1"}, request=httpx.Request("POST", "https://example.invalid")
        )
        raise openai.RateLimitError(
            "rate limit", response=response,
            body={"code": "insufficient_quota" if reason == "quota" else "rate_limit_exceeded"},
        )

    captured = {}

    def client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(responses=SimpleNamespace(parse=parse))

    monkeypatch.setattr(openai, "OpenAI", client)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", sleeps.append)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_OPENAI_MAX_RETRIES", 1)
    result = limited.post("/api/v1/clientes/AZ-test/recomendacao", headers=headers())
    assert result.status_code == 200
    assert result.json()["origem"] == "llm-indisponivel"
    assert len(calls) == (1 if reason == "quota" else 2)
    assert sleeps == ([] if reason == "quota" else [1.0])
    assert captured["max_retries"] == 0
