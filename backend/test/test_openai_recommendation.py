import json
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai.llm.openai_recommendation import (
    MAX_RATE_LIMIT_ATTEMPTS,
    OpenAIRecommendationError,
    OpenAIRecommendationService,
    RecommendationOutput,
)


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


class FakeAPIStatusError(Exception):
    pass


class FakeRateLimitError(FakeAPIStatusError):
    pass


class FakeAPIConnectionError(Exception):
    pass


class FakeAPITimeoutError(FakeAPIConnectionError):
    pass


def _install_openai(monkeypatch, parse, captured=None):
    def fake_openai_client(**kwargs):
        if captured is not None:
            captured["client"] = kwargs
        return SimpleNamespace(
            responses=SimpleNamespace(
                parse=lambda **request: parse(request, captured)
            )
        )

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(
            OpenAI=fake_openai_client,
            APIConnectionError=FakeAPIConnectionError,
            APIStatusError=FakeAPIStatusError,
            APITimeoutError=FakeAPITimeoutError,
            RateLimitError=FakeRateLimitError,
        ),
    )


def _valid_output():
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


def test_openai_uses_structured_output_and_excludes_client_identifier(monkeypatch):
    captured = {}
    output = _valid_output()
    _install_openai(
        monkeypatch,
        lambda request, result: (
            result.__setitem__("request", request)
            or SimpleNamespace(output_parsed=output)
        ),
        captured,
    )

    result = OpenAIRecommendationService(
        "test-key-not-a-real-secret",
        "gpt-test",
        timeout_seconds=4,
    ).recommend(_state())

    assert result is output
    assert captured["client"]["timeout"] == 4
    assert captured["client"]["max_retries"] == 0
    request = captured["request"]
    assert request["model"] == "gpt-test"
    assert request["text_format"] is RecommendationOutput
    user_prompt = request["input"][1]["content"]
    assert "must-not-leave-the-backend" not in user_prompt
    profile = json.loads(user_prompt)
    assert profile["churn_score_target"] == "high_risk_flag; not observed churn"
    assert profile["graph_rag_context"]["policies_verified"] is False
    system_prompt = request["input"][0]["content"]
    assert "Diferencie explicitamente políticas marcadas como verificadas" in system_prompt
    assert "Toda oferta deve ser hipotética, demonstrativa" in system_prompt


def test_openai_schema_rejects_nonzero_offer_amounts():
    output = RecommendationOutput(
        action_code="comunicacao",
        strategy="Contato de relacionamento",
        reasoning="Validar com um analista.",
        channel="App",
        message="Demonstração não verificada.",
        benefit="Validar opções.",
        bonus_points=0,
        voucher_value=0.0,
        evidence=[],
    )

    with pytest.raises(ValidationError):
        RecommendationOutput.model_validate(
            output.model_dump() | {"bonus_points": 1000}
        )


def test_openai_rejects_unparsed_response(monkeypatch):
    _install_openai(
        monkeypatch,
        lambda _request, _captured: SimpleNamespace(output_parsed=None),
    )

    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())
    assert exc.value.reason == "invalid_response"


def test_openai_rejects_schema_validation_error(monkeypatch):
    def parse(_request, _captured):
        RecommendationOutput.model_validate({"action_code": "invalid"})

    _install_openai(monkeypatch, parse)

    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())

    assert exc.value.reason == "invalid_response"


def test_openai_requires_a_configured_key():
    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("", "gpt-test").recommend(_state())
    assert exc.value.reason == "not_configured"


def test_temporary_rate_limit_retries_and_then_succeeds(monkeypatch):
    calls = []
    sleeps = []
    output = _valid_output()

    def parse(_request, _captured):
        calls.append(None)
        if len(calls) == 1:
            error = FakeRateLimitError("sensitive detail must not be logged")
            error.response = SimpleNamespace(headers={"retry-after": "3"})
            raise error
        return SimpleNamespace(output_parsed=output)

    _install_openai(monkeypatch, parse)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", sleeps.append)

    result = OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())

    assert result is output
    assert len(calls) == 2
    assert sleeps == [3.0]


def test_persistent_rate_limit_stops_after_bounded_attempts(monkeypatch):
    calls = []
    sleeps = []

    def parse(_request, _captured):
        calls.append(None)
        raise FakeRateLimitError("temporary rate limit")

    _install_openai(monkeypatch, parse)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", sleeps.append)

    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())

    assert exc.value.reason == "rate_limit"
    assert len(calls) == MAX_RATE_LIMIT_ATTEMPTS
    assert sleeps == [0.5, 1.0]


def test_quota_error_falls_back_without_retry(monkeypatch):
    calls = []
    sleeps = []

    def parse(_request, _captured):
        calls.append(None)
        error = FakeRateLimitError("quota detail must not be logged")
        error.body = {
            "error": {"code": "insufficient_quota", "message": "private billing detail"}
        }
        raise error

    _install_openai(monkeypatch, parse)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", sleeps.append)

    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())

    assert exc.value.reason == "quota_billing"
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    ("error_type", "reason"),
    [
        (FakeAPITimeoutError, "timeout"),
        (FakeAPIConnectionError, "connection_error"),
        (FakeAPIStatusError, "api_status_error"),
    ],
)
def test_permanent_or_transport_errors_are_classified_without_retry(
    monkeypatch, error_type, reason
):
    calls = []
    sleeps = []

    def parse(_request, _captured):
        calls.append(None)
        raise error_type("private exception detail")

    _install_openai(monkeypatch, parse)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", sleeps.append)

    with pytest.raises(OpenAIRecommendationError) as exc:
        OpenAIRecommendationService("test-key", "gpt-test").recommend(_state())

    assert exc.value.reason == reason
    assert len(calls) == 1
    assert sleeps == []


def test_retry_rate_limit_does_not_log_error_payload_or_secret(monkeypatch, caplog):
    error_text = "test-api-key private-client-id"
    calls = []

    def parse(_request, _captured):
        calls.append(None)
        raise FakeRateLimitError(error_text)

    _install_openai(monkeypatch, parse)
    monkeypatch.setattr("ai.llm.openai_recommendation.time.sleep", lambda _delay: None)

    with pytest.raises(OpenAIRecommendationError):
        OpenAIRecommendationService("test-api-key", "gpt-test").recommend(_state())

    assert error_text not in caplog.text
    assert "test-api-key" not in caplog.text
    assert "private-client-id" not in caplog.text
