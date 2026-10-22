import hashlib
import hmac
import logging
import math
import time
from functools import lru_cache
from threading import Lock
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.config import settings
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

# Check both barriers before incrementing either; expiry is set on first use.
_CONSUME_SCRIPT = """
local retry = 0
for i, key in ipairs(KEYS) do
    local count = tonumber(redis.call('GET', key) or '0')
    if count >= tonumber(ARGV[i + 1]) then
        local ttl = redis.call('PTTL', key)
        if ttl < 0 then
            return redis.error_reply('Rate limit counter has no expiry')
        end
        retry = math.max(retry, ttl, 1)
    end
end
if retry > 0 then return retry end
for _, key in ipairs(KEYS) do
    if redis.call('INCR', key) == 1 then
        redis.call('PEXPIRE', key, ARGV[1])
    end
end
return 0
"""


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    def consume(self, limits: dict[str, int], window: int) -> int:
        with self._lock:
            now = time.monotonic()
            self._entries = {
                key: value for key, value in self._entries.items() if value[1] > now
            }
            retry = max(
                (
                    self._entries[key][1] - now
                    for key, limit in limits.items()
                    if key in self._entries and self._entries[key][0] >= limit
                ),
                default=0,
            )
            if retry > 0:
                return max(1, math.ceil(retry))
            for key in limits:
                count, expires = self._entries.get(key, (0, now + window))
                self._entries[key] = (count + 1, expires)
            return 0


memory_limiter = MemoryRateLimiter()


@lru_cache(maxsize=1)
def redis_client(url: str) -> Redis:
    return Redis.from_url(
        url,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry=Retry(NoBackoff(), 0),
    )


def validate_ai_rate_limit_settings() -> None:
    if min(
        settings.AI_RATE_LIMIT_REQUESTS,
        settings.AI_RATE_LIMIT_IP_REQUESTS,
        settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    ) <= 0:
        raise RuntimeError("AI_RATE_LIMIT: limites e janela devem ser maiores que zero.")
    if not 0 <= settings.AI_OPENAI_MAX_RETRIES <= 2:
        raise RuntimeError("AI_OPENAI_MAX_RETRIES deve estar entre 0 e 2.")
    if not settings.AI_RATE_LIMIT_ENABLED:
        return
    if settings.REDIS_URL:
        try:
            parsed = urlsplit(settings.REDIS_URL)
            valid = parsed.scheme in {"redis", "rediss"} and parsed.hostname and (
                parsed.port is None or parsed.port > 0
            )
        except ValueError:
            valid = False
        if not valid:
            raise RuntimeError("REDIS_URL deve ser uma URL redis:// ou rediss:// válida.")
    elif settings.is_production:
        raise RuntimeError("REDIS_URL é obrigatório para AI_RATE_LIMIT em produção.")


def _key(kind: str, identity: str) -> str:
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        f"{kind}:{identity}".encode(),
        hashlib.sha256,
    ).hexdigest()
    # The hash tag keeps both counters in one Redis Cluster slot.
    return f"crm:{{ai-rate-limit}}:{kind}:{digest}"


def enforce_ai_rate_limit(
    request: Request, current_user: dict = Depends(get_current_user)
) -> None:
    if not settings.AI_RATE_LIMIT_ENABLED:
        return
    subject = current_user.get("sub")
    limits = {}
    if isinstance(subject, str) and subject.strip():
        limits[_key("user", subject)] = settings.AI_RATE_LIMIT_REQUESTS
    if request.client:
        # Proxy headers are not read here; trust only the ASGI peer configured by deployment.
        limits[_key("ip", request.client.host)] = (
            settings.AI_RATE_LIMIT_IP_REQUESTS if limits else settings.AI_RATE_LIMIT_REQUESTS
        )
    if not limits:
        logger.error("AI request has neither authenticated subject nor peer address.")
        raise HTTPException(503, detail={
            "code": "AI_RATE_LIMIT_UNAVAILABLE",
            "message": "Não foi possível verificar o limite de IA. Tente novamente.",
        })
    try:
        validate_ai_rate_limit_settings()
        if settings.REDIS_URL:
            milliseconds = redis_client(settings.REDIS_URL).eval(
                _CONSUME_SCRIPT,
                len(limits),
                *limits,
                settings.AI_RATE_LIMIT_WINDOW_SECONDS * 1000,
                *limits.values(),
            )
            retry = max(0, math.ceil(int(milliseconds) / 1000))
        else:
            retry = memory_limiter.consume(limits, settings.AI_RATE_LIMIT_WINDOW_SECONDS)
    except (RedisError, RuntimeError, ValueError):
        logger.error("AI rate limiter unavailable; request blocked before recommendation.")
        raise HTTPException(503, detail={
            "code": "AI_RATE_LIMIT_UNAVAILABLE",
            "message": "Proteção de IA temporariamente indisponível. Tente novamente.",
        }) from None
    if retry:
        raise HTTPException(
            429,
            detail={
                "code": "AI_RATE_LIMIT_EXCEEDED",
                "message": "Muitas solicitações de IA. Tente novamente em instantes.",
            },
            headers={"Retry-After": str(retry)},
        )
