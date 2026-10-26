from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"LLM recommendation unavailable: {reason}")


class RecommendationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_code: Literal[
        "recuperacao-servico",
        "bonus-pontos",
        "upgrade",
        "comunicacao",
    ]
    strategy: str = Field(min_length=1, max_length=120)
    reasoning: str = Field(min_length=1, max_length=500)
    channel: Literal["App", "E-mail", "SMS", "Telefone"]
    message: str = Field(min_length=1, max_length=500)
    benefit: str = Field(min_length=1, max_length=200)
    bonus_points: int = Field(ge=0, le=0)
    voucher_value: float = Field(ge=0, le=0)
    evidence: list[str] = Field(max_length=8)


class RecommendationProvider(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    def recommend(self, state: dict) -> RecommendationOutput: ...


RECOMMENDATION_SYSTEM_PROMPT = (
    "Crie uma recomendação curta para um analista de relacionamento. "
    "Use somente os dados e premissas fornecidos; não afirme que "
    "benefícios, vouchers ou políticas são direitos confirmados. "
    "Diferencie explicitamente políticas marcadas como verificadas "
    "das não verificadas, sem inferir elegibilidade individual. "
    "Toda oferta deve ser hipotética, demonstrativa e identificada "
    "como não verificada; não afirme crédito, concessão ou direito. "
    "Use voucher_value=0 e bonus_points=0. As regras podem ser "
    "ilustrativas e não verificadas. Não invente incidentes, "
    "consentimento, fatos ou benefícios. Se não houver score, não "
    "o trate como alto nem como baixo. Não solicite nem inclua "
    "identificadores pessoais."
)


def recommendation_profile(state: dict) -> dict:
    return {
        "tier": state["tier"],
        "frequency": state["frequency"],
        "total_spend": state["total_spend"],
        "churn_score": state["churn_score"],
        "churn_score_target": "high_risk_flag; not observed churn",
        "flight_incidents": state["flight_incidents"],
        "incident_type": state["incident_type"],
        "value_at_risk": state["value_at_risk"],
        "clv_12m": state.get("clv_12m"),
        "graph_rag_context": state["graph_rag_context"],
    }
