import pytest

from app.config import settings
from app.core import ai_rate_limit


@pytest.fixture(autouse=True)
def isolate_ai_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "REDIS_URL", "")
    monkeypatch.setattr(ai_rate_limit, "memory_limiter", ai_rate_limit.MemoryRateLimiter())
