import logging

from ai.llm.contracts import (
    LLMProviderError,
    RecommendationOutput,
    RecommendationProvider,
)
from ai.llm.gemini_recommendation import GeminiRecommendationService
from ai.llm.openai_recommendation import OpenAIRecommendationService
from app.config import Settings, settings

logger = logging.getLogger(__name__)
SUPPORTED_PROVIDERS = {"openai", "gemini", "disabled"}


class DisabledRecommendationProvider:
    name = "disabled"
    configured = False

    def recommend(self, state: dict) -> RecommendationOutput:
        raise LLMProviderError("disabled")


class LLMRecommendationService:
    def __init__(
        self,
        primary: RecommendationProvider,
        fallback: RecommendationProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    def recommend(self, state: dict) -> RecommendationOutput | None:
        if self._primary.name == "disabled":
            return None
        if not self._primary.configured:
            error = LLMProviderError("not_configured")
            return self._try_fallback(state, error)
        try:
            return self._primary.recommend(state)
        except LLMProviderError as error:
            return self._try_fallback(state, error)

    def _try_fallback(
        self, state: dict, primary_error: LLMProviderError
    ) -> RecommendationOutput | None:
        if self._fallback.name == "disabled":
            if primary_error.reason == "not_configured":
                logger.info("Selected LLM provider is not configured; using rules.")
                return None
            raise primary_error
        if not self._fallback.configured:
            logger.warning(
                "Configured fallback provider is not configured; provider=%s.",
                self._fallback.name,
            )
            raise primary_error

        logger.warning(
            "Selected LLM provider unavailable; trying explicitly configured fallback; "
            "reason=%s.",
            primary_error.reason,
        )
        try:
            return self._fallback.recommend(state)
        except LLMProviderError as fallback_error:
            logger.warning(
                "Configured fallback provider unavailable; provider=%s; reason=%s.",
                self._fallback.name,
                fallback_error.reason,
            )
            raise fallback_error from primary_error


def _create_provider(provider_name: str, configuration: Settings) -> RecommendationProvider:
    if provider_name == "disabled":
        return DisabledRecommendationProvider()
    if provider_name == "openai":
        return OpenAIRecommendationService(
            configuration.OPENAI_API_KEY,
            configuration.OPENAI_MODEL,
            configuration.OPENAI_TIMEOUT_SECONDS,
            max_retries=configuration.AI_OPENAI_MAX_RETRIES,
        )
    if provider_name == "gemini":
        return GeminiRecommendationService(
            configuration.GEMINI_API_KEY,
            configuration.GEMINI_MODEL,
            configuration.GEMINI_TIMEOUT_SECONDS,
        )
    raise ValueError("Provider LLM não suportado.")


def create_llm_service(configuration: Settings = settings) -> LLMRecommendationService:
    primary_name = configuration.LLM_PROVIDER
    fallback_name = configuration.LLM_FALLBACK_PROVIDER
    if primary_name not in SUPPORTED_PROVIDERS:
        raise ValueError("LLM_PROVIDER não suportado.")
    if fallback_name not in SUPPORTED_PROVIDERS:
        raise ValueError("LLM_FALLBACK_PROVIDER não suportado.")
    if primary_name == "disabled" and fallback_name != "disabled":
        raise ValueError("LLM_FALLBACK_PROVIDER deve ser 'disabled' quando LLM_PROVIDER for 'disabled'.")
    if fallback_name == primary_name and primary_name != "disabled":
        raise ValueError("LLM_FALLBACK_PROVIDER não pode repetir LLM_PROVIDER.")

    return LLMRecommendationService(
        _create_provider(primary_name, configuration),
        _create_provider(fallback_name, configuration),
    )
