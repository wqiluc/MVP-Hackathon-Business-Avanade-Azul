from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model

CHURN_FEATURES = (
    "dias_desde_ultimo_voo",
    "voos_12m",
    "voos_6m",
    "voos_3m",
    "voos_6m_anteriores",
    "variacao_voos_6m_vs_anteriores",
    "intervalo_medio_entre_voos",
    "gasto_total_12m",
    "ticket_medio_12m",
    "pontos_acumulados_12m",
    "gasto_extras_12m",
    "antecedencia_media",
    "pct_viagens_negocios",
    "pct_classe_premium",
    "pct_classe_flex",
    "num_rotas_distintas",
    "concentracao_rota_favorita",
    "pct_voos_internacionais",
    "n_passageiros_medio_compra",
    "pct_pago_com_pontos",
    "pct_pago_misto_pontos_dinheiro",
    "valor_desconto_pontos_12m",
    "pontos_usados_compra_12m",
    "pct_compra_canal_proprio",
    "pct_compra_agencia_ota",
    "pct_compra_corporativo",
    "possui_cartao_cobrand",
    "pct_pago_cartao_cobrand",
    "pct_pago_cartao_bandeira_parceira",
    "pct_pago_cartao_terceiro",
    "pct_voos_alta_temporada",
    "concentracao_trimestre_favorito",
    "voos_mesma_janela_ano_anterior",
    "meses_distintos_voados",
    "pct_voos_atrasados",
    "minutos_atraso_medio",
    "n_cancelamentos_12m",
    "n_avaliacoes_12m",
    "sentimento_medio_12m",
    "n_remarcacoes_12m",
    "n_reembolsos_12m",
    "pct_checkin_app",
    "tier_idx",
    "saldo_pontos",
    "pct_pontos_resgatados",
    "tempo_de_programa_meses",
    "contatos_crm_6m",
    "taxa_abertura_6m",
    "taxa_conversao_6m",
    "aceita_marketing",
    "canal_aquisicao",
    "tipo_cliente",
)

STRING_FEATURES = frozenset({"canal_aquisicao", "tipo_cliente"})

# Exact MLflow signature types for workspace.default.clv_gb v3.
CLV_INTEGER_FEATURES = frozenset(
    {
        "dias_desde_ultimo_voo",
        "voos_12m",
        "voos_6m",
        "voos_3m",
        "voos_6m_anteriores",
        "pontos_acumulados_12m",
        "num_rotas_distintas",
        "valor_desconto_pontos_12m",
        "pontos_usados_compra_12m",
        "possui_cartao_cobrand",
        "voos_mesma_janela_ano_anterior",
        "meses_distintos_voados",
        "n_cancelamentos_12m",
        "n_avaliacoes_12m",
        "n_remarcacoes_12m",
        "n_reembolsos_12m",
        "tier_idx",
        "saldo_pontos",
        "contatos_crm_6m",
        "aceita_marketing",
    }
)


def _feature_contract(name: str, integer_features: frozenset[str]):
    fields: dict[str, tuple[type, object]] = {}
    for feature in CHURN_FEATURES:
        if feature in STRING_FEATURES:
            field_type = str
        elif feature in integer_features:
            field_type = int
        else:
            field_type = float
        fields[feature] = (field_type, ...)
    return create_model(
        name,
        __config__=ConfigDict(extra="forbid", strict=True),
        **fields,
    )


ChurnFeatures = _feature_contract("ChurnFeatures", frozenset())
ClvFeatures = _feature_contract("ClvFeatures", CLV_INTEGER_FEATURES)


class PredictionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    model_version: str | None
    source: Literal["local", "databricks"]
    timestamp: datetime

class ChurnPrediction(PredictionMetadata):
    score: float


class ClvPrediction(PredictionMetadata):
    value: float
