import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai.llm.contracts import LLMProviderError, RecommendationOutput
from ai.llm.gemini_recommendation import (
    GeminiRecommendationError,
    GeminiRecommendationService,
)
from ai.llm.openai_recommendation import OpenAIRecommendationService
from app.services.llm_provider_factory import (
    DisabledRecommendationProvider,
    LLMRecommendationService,
    create_llm_service,
)
from app.config import Settings


class FakeGeminiAPIError(Exception):
    def __init__(self, code):
        self.code = code


def _state():
    return {
        "client_identifier": "must-not-leave-the-backend",
        "tier": "Safira",
        "frequency": 12,
        "total_spend": 12000.0,
        "churn_score": 0.72,
        "flight_incidents": 0,
        "incident_type": None,
        "value_at_risk": 11232.0,
        "graph_rag_context": {
            "policy_context": "Premissa ilustrativa não verificada.",
            "graph_relations": ["Safira -> categorias"],
            "policies_verified": False,
        },
    }


def _output():
    return RecommendationOutput(
        action_code="comunicacao",
        strategy="Contato de relacionamento",
        reasoning="Revisar as necessidades antes de sugerir opções.",
        channel="App",
        message="Um analista pode entrar em contato para entender suas necessidades.",
        benefit="Validar opções disponíveis com um analista.",
        bonus_points=0,
        voucher_value=0.0,
        evidence=["Safira -> categorias"],
    )


def _install_gemini(monkeypatch, response_text, captured, error=None):
    def generate_content(**request):
        captured["request"] = request
        if error is not None:
            raise error
        return SimpleNamespace(text=response_text)

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content),
        close=Mock(),
    )

    class HttpOptions:
        def __init__(self, **kwargs):
            captured["http_options"] = kwargs

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            captured["config"] = kwargs

    fake_genai = SimpleNamespace(Client=lambda **kwargs: client)
    fake_types = SimpleNamespace(
        HttpOptions=HttpOptions,
        GenerateContentConfig=GenerateContentConfig,
    )
    fake_errors = SimpleNamespace(APIError=FakeGeminiAPIError)
    monkeypatch.setitem(
        sys.modules,
        "google",
        SimpleNamespace(genai=fake_genai),
    )
    monkeypatch.setitem(
        sys.modules,
        "google.genai",
        SimpleNamespace(types=fake_types, errors=fake_errors),
    )
    return client


def test_gemini_uses_shared_structured_contract_and_excludes_client_identifier(
    monkeypatch,
):
    captured = {}
    output = _output()
    client = _install_gemini(
        monkeypatch,
        output.model_dump_json(),
        captured,
    )

    result = GeminiRecommendationService(
        "test-gemini-key", "gemini-test", timeout_seconds=4
    ).recommend(_state())

    assert result == output
    assert captured["http_options"] == {"timeout": 4000}
    request = captured["request"]
    assert request["model"] == "gemini-test"
    assert captured["config"]["response_mime_type"] == "application/json"
    assert captured["config"]["response_schema"] is RecommendationOutput
    assert captured["config"]["system_instruction"]
    assert "must-not-leave-the-backend" not in request["contents"]
    profile = json.loads(request["contents"])
    assert profile["churn_score_target"] == "high_risk_flag; not observed churn"
    client.close.assert_called_once()


def test_gemini_invalid_structured_response_is_rejected_without_echoing_payload(
    monkeypatch, caplog
):
    captured = {}
    client = _install_gemini(
        monkeypatch,
        '{"action_code":"invalid","secret":"not-for-logs"}',
        captured,
    )
    service = GeminiRecommendationService("test-key", "gemini-test")
    state = _state()

    with pytest.raises(GeminiRecommendationError) as exc:
        service.recommend(state)

    assert exc.value.reason == "invalid_response"
    assert "not-for-logs" not in caplog.text
    client.close.assert_called_once()


def test_gemini_api_error_is_safely_classified(monkeypatch, caplog):
    captured = {}
    error = FakeGeminiAPIError(429)
    error.args = ("secret-bearing provider response",)
    _install_gemini(monkeypatch, "", captured, error=error)
    service = GeminiRecommendationService("test-key", "gemini-test")
    state = _state()

    with pytest.raises(GeminiRecommendationError) as exc:
        service.recommend(state)

    assert exc.value.reason == "rate_limit"
    assert "secret-bearing provider response" not in caplog.text


def test_gemini_requires_key_and_model():
    service = GeminiRecommendationService("", "")
    state = _state()
    assert not service.configured
    with pytest.raises(GeminiRecommendationError) as exc:
        service.recommend(state)
    assert exc.value.reason == "not_configured"


def test_factory_resolves_each_supported_provider():
    openai_settings = Settings(
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-test",
        LLM_FALLBACK_PROVIDER="disabled",
    )
    gemini_settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL="gemini-test",
        LLM_FALLBACK_PROVIDER="disabled",
    )
    disabled_settings = Settings(
        LLM_PROVIDER="disabled",
        LLM_FALLBACK_PROVIDER="disabled",
    )

    assert isinstance(create_llm_service(openai_settings)._primary, OpenAIRecommendationService)
    assert isinstance(
        create_llm_service(gemini_settings)._primary, GeminiRecommendationService
    )
    disabled = create_llm_service(disabled_settings)
    assert disabled.recommend(_state()) is None


def test_disabled_provider_does_not_invoke_explicit_fallback():
    fallback = Mock()
    fallback.name = "openai"
    fallback.configured = True
    service = LLMRecommendationService(
        DisabledRecommendationProvider(),
        fallback,
    )

    assert service.recommend(_state()) is None
    fallback.recommend.assert_not_called()


def test_provider_failure_does_not_call_fallback_without_explicit_configuration():
    primary = Mock()
    primary.name = "gemini"
    primary.configured = True
    primary.recommend.side_effect = LLMProviderError("api_status_error")
    fallback = DisabledRecommendationProvider()
    service = LLMRecommendationService(primary, fallback)
    state = _state()

    with pytest.raises(LLMProviderError, match="api_status_error"):
        service.recommend(state)

    primary.recommend.assert_called_once()


def test_provider_failure_uses_only_explicitly_configured_fallback():
    primary = Mock()
    primary.name = "gemini"
    primary.configured = True
    primary.recommend.side_effect = LLMProviderError("api_status_error")
    fallback = Mock()
    fallback.name = "openai"
    fallback.configured = True
    fallback.recommend.return_value = _output()
    service = LLMRecommendationService(primary, fallback)

    assert service.recommend(_state()) == _output()
    primary.recommend.assert_called_once()
    fallback.recommend.assert_called_once()


@pytest.mark.parametrize(
    ("configuration", "reason"),
    [
        (
            Settings(LLM_PROVIDER="ollama", LLM_FALLBACK_PROVIDER="disabled"),
            "não suportado",
        ),
        (
            Settings(LLM_PROVIDER="gemini", LLM_FALLBACK_PROVIDER="gemini"),
            "não pode repetir",
        ),
        (
            Settings(LLM_PROVIDER="disabled", LLM_FALLBACK_PROVIDER="gemini"),
            "deve ser 'disabled'",
        ),
    ],
)
def test_factory_rejects_implicit_or_duplicate_provider_fallback(
    configuration, reason
):
    with pytest.raises(ValueError, match=reason):
        create_llm_service(configuration)
