import json
import logging
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pydantic import ValidationError

from ai.llm.contracts import (
    LLMProviderError,
    RECOMMENDATION_SYSTEM_PROMPT,
    RecommendationOutput,
    recommendation_profile,
)

logger = logging.getLogger(__name__)

MAX_RATE_LIMIT_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 0.5


class OpenAIRecommendationError(LLMProviderError):
    pass


def _error_details(error: Exception) -> str:
    values = [
        getattr(error, "code", None),
        getattr(error, "type", None),
        getattr(error, "message", None),
    ]
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body_error = body.get("error")
        if isinstance(body_error, dict):
            values.extend(body_error.get(key) for key in ("code", "type", "message"))
    return " ".join(value for value in values if isinstance(value, str)).lower()


def _is_quota_error(error: Exception) -> bool:
    details = _error_details(error)
    return any(
        marker in details
        for marker in (
            "insufficient_quota",
            "billing",
            "quota",
            "credit balance",
            "usage limit",
        )
    )


def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    value = headers.get("retry-after")
    if not isinstance(value, str):
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if math.isfinite(seconds) else None
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _rate_limit_delay(error: Exception, retry_number: int) -> float:
    backoff = INITIAL_BACKOFF_SECONDS * (2 ** (retry_number - 1))
    retry_after = _retry_after_seconds(error)
    return max(backoff, retry_after) if retry_after is not None else backoff


class OpenAIRecommendationService:
    name = "openai"

    def __init__(
        self, api_key: str, model: str, timeout_seconds: float = 12,
        max_retries: int = MAX_RATE_LIMIT_ATTEMPTS - 1,
    ) -> None:
        if not 0 <= max_retries <= 2:
            raise ValueError("max_retries must be between 0 and 2")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_retries + 1

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    def recommend(self, state: dict) -> RecommendationOutput:
        if not self.configured:
            raise OpenAIRecommendationError("not_configured")

        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            OpenAI,
            RateLimitError,
        )

        client = OpenAI(
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            max_retries=0,
        )
        profile = recommendation_profile(state)
        request = {
            "model": self._model,
            "input": [
                {
                    "role": "system",
                    "content": RECOMMENDATION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(profile, ensure_ascii=False, allow_nan=False),
                },
            ],
            "text_format": RecommendationOutput,
        }
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = client.responses.parse(**request)
                break
            except RateLimitError as error:
                if _is_quota_error(error):
                    logger.warning("OpenAI request rejected for quota/billing.")
                    raise OpenAIRecommendationError("quota_billing") from error
                if attempt == self._max_attempts:
                    logger.warning("OpenAI rate limit persisted after bounded retries.")
                    raise OpenAIRecommendationError("rate_limit") from error
                delay = _rate_limit_delay(error, attempt)
                if delay > self._timeout_seconds:
                    logger.warning("OpenAI retry delay exceeds request wait budget; using fallback.")
                    raise OpenAIRecommendationError("rate_limit") from error
                logger.info(
                    "OpenAI temporary rate limit; retry %d/%d after %.2f seconds.",
                    attempt,
                    self._max_attempts - 1,
                    delay,
                )
                time.sleep(delay)
            except APITimeoutError as error:
                logger.warning("OpenAI request timed out.")
                raise OpenAIRecommendationError("timeout") from error
            except APIConnectionError as error:
                logger.warning("OpenAI connection failed.")
                raise OpenAIRecommendationError("connection_error") from error
            except APIStatusError as error:
                logger.warning("OpenAI returned a non-retryable API status error.")
                raise OpenAIRecommendationError("api_status_error") from error
            except ValidationError as error:
                logger.warning("OpenAI returned an invalid structured response.")
                raise OpenAIRecommendationError("invalid_response") from error

        parsed = response.output_parsed
        if not isinstance(parsed, RecommendationOutput):
            raise OpenAIRecommendationError("invalid_response")
        return parsed
