import json
import logging

import httpx
from pydantic import ValidationError

from ai.llm.contracts import (
    LLMProviderError,
    RECOMMENDATION_SYSTEM_PROMPT,
    RecommendationOutput,
    recommendation_profile,
)

logger = logging.getLogger(__name__)


class GeminiRecommendationError(LLMProviderError):
    pass


class GeminiRecommendationService:
    name = "gemini"

    def __init__(
        self, api_key: str, model: str, timeout_seconds: float = 12
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    def recommend(self, state: dict) -> RecommendationOutput:
        if not self.configured:
            raise GeminiRecommendationError("not_configured")

        from google import genai
        from google.genai import errors, types

        try:
            client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=int(self._timeout_seconds * 1000)
                ),
            )
        except (errors.APIError, httpx.TimeoutException, httpx.TransportError) as error:
            logger.warning("Gemini client initialization failed.")
            raise GeminiRecommendationError("connection_error") from error

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=json.dumps(
                    recommendation_profile(state),
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                config=types.GenerateContentConfig(
                    system_instruction=RECOMMENDATION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RecommendationOutput,
                ),
            )
        except httpx.TimeoutException as error:
            logger.warning("Gemini request timed out.")
            raise GeminiRecommendationError("timeout") from error
        except httpx.TransportError as error:
            logger.warning("Gemini connection failed.")
            raise GeminiRecommendationError("connection_error") from error
        except errors.APIError as error:
            reason = "rate_limit" if getattr(error, "code", None) == 429 else "api_status_error"
            logger.warning("Gemini returned an API error; category=%s.", reason)
            raise GeminiRecommendationError(reason) from error
        finally:
            client.close()

        try:
            if not isinstance(response.text, str) or not response.text.strip():
                raise GeminiRecommendationError("invalid_response")
            return RecommendationOutput.model_validate_json(response.text)
        except (ValidationError, ValueError) as error:
            logger.warning("Gemini returned an invalid structured response.")
            raise GeminiRecommendationError("invalid_response") from error
