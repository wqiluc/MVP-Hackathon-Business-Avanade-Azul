import logging
import pandas as pd

from app.config import settings
from app.services.datalake_service import DataLakeService
from app.services.agent_service import invoke_agent_workflow

logger = logging.getLogger(__name__)

DATA_REFERENCIA = "2026-09-30"
MESES = ["out/25", "nov/25", "dez/25", "jan/26", "fev/26", "mar/26",
         "abr/26", "mai/26", "jun/26", "jul/26", "ago/26", "set/26"]
TIERS = ["Básico", "Topázio", "Safira", "Diamante"]
PERSONAS = ["executivo-frequente", "lazer-premium", "regional-conectado", "potencial-ascensao"]
RISCO_ALTO = 0.5
SCORE_ALTO_VALOR = 70
_DEMONSTRATION_NOTICE = (
    "Demonstração: esta sugestão não confirma oferta vigente nem elegibilidade "
    "individual. Valide as regras antes de comunicar ou aplicar qualquer benefício."
)

_TIER_MAP = {"BASICO": "Básico", "BÁSICO": "Básico", "TOPAZIO": "Topázio", "TOPÁZIO": "Topázio",
             "SAFIRA": "Safira", "DIAMANTE": "Diamante"}


def _tier(valor) -> str:
    normalized = str(valor).strip()
    return _TIER_MAP.get(normalized.upper(), normalized.title() or "Não informado")


def _persona(row) -> str:
    if row.tier == "Diamante" or (row.frequency >= 18 and row.avg_ticket >= 1500):
        return "executivo-frequente"
    if row.avg_ticket >= 2500:
        return "lazer-premium"
    if row.frequency >= 10:
        return "regional-conectado"
    return "potencial-ascensao"


def _nivel(risco: float) -> str:
    return "critico" if risco >= 0.7 else "alto" if risco >= RISCO_ALTO else "moderado" if risco >= 0.3 else "baixo"


def _acao_regras(risco: float | None, tier: str, incidentes: int) -> dict:
    if incidentes >= 2:
        tipo, titulo, canal = (
            "recuperacao-servico",
            "Revisar incidentes com atendimento",
            "Telefone",
        )
    elif risco is not None and risco >= RISCO_ALTO:
        tipo, titulo, canal = "comunicacao", "Contato de relacionamento", "E-mail"
    else:
        tipo, titulo, canal = "comunicacao", "Contato informativo", "App"
    justificativa = (
        [
            f"Score de classificação high_risk_flag: {risco:.0%}; "
            "não é churn observado."
        ]
        if risco is not None
        else ["Score indisponível até o registro e a disponibilização do modelo."]
    )
    return {
        "tipo": tipo, "titulo": titulo, "canal": canal,
        "justificativa": [*justificativa, f"Categoria CRM: {tier}"],
        "mensagem": (
            "Um analista pode entender sua necessidade e verificar as opções disponíveis."
        ),
        "regrasFidelidade": [],
        "confianca": None,
        "origem": "regras",
        "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
    }


def _linha_para_cliente(r) -> dict:
    tier = _tier(r.tier)
    raw_score = getattr(r, "churn_score", None)
    risco = float(raw_score) if raw_score is not None and pd.notna(raw_score) else None
    receita = float(r.total_spend)
    clv = round(receita * 2 * (1 - risco * 0.5), 2) if risco is not None else round(receita * 2, 2)
    score = round(min(100, 100 * (0.4 * min(receita / 60000, 1) + 0.35 * min(r.frequency / 24, 1)
                                  + 0.25 * max(0, 1 - r.recency_days / 180))), 1)
    persona = _persona(type("R", (), {"tier": tier, "frequency": r.frequency, "avg_ticket": float(r.avg_ticket or 0)}))
    pesos = [1 / len(MESES)] * len(MESES)
    acao = _acao_regras(risco, tier, int(r.flight_incidents))
    return {
        "id": r.client_identifier, "nome": r.client_identifier, "tier": tier, "persona": persona,
        "aeroportoBase": "—", "cidadeBase": "—", "membroDesde": DATA_REFERENCIA,
        "consentimentoMarketing": None,
        "clvProjetado": clv, "scoreValor": score, "riscoEvasao": round(risco, 3) if risco is not None else None,
        "_churn_score": risco, "_flight_incidents": int(r.flight_incidents),
        "_incident_type": None,
        "recenciaDias": int(r.recency_days), "voos12m": int(r.frequency), "receita12m": receita,
        "ticketMedio": float(r.avg_ticket or 0), "saldoPontos": 0, "pontosQualificaveis": 0,
        "sentimentoScore": round(max(-1, 1 - 0.5 * int(r.flight_incidents)), 2),
        "rotasFavoritas": [],
        "historico": [{"mes": m, "voos": round(r.frequency * p, 2), "receita": round(receita * p, 2)}
                      for m, p in zip(MESES, pesos)],
        "interacoes": [],
        "explicacaoValor": [
            {"fator": "Gasto total", "valor": f"R$ {receita:,.0f}", "impacto": round(0.4 * min(receita / 60000, 1) * 100, 1)},
            {"fator": "Frequência", "valor": f"{int(r.frequency)} voos", "impacto": round(0.35 * min(r.frequency / 24, 1) * 100, 1)},
        ],
        "explicacaoRisco": [
            {"fator": "Recência", "valor": f"{int(r.recency_days)} dias", "impacto": round(45 * min(r.recency_days / 180, 1), 1)},
            {"fator": "Incidentes de voo", "valor": str(int(r.flight_incidents)), "impacto": round(12 * min(r.flight_incidents, 3), 1)},
        ],
        "proximaAcao": acao,
    }


def _resumo(c: dict) -> dict:
    return {k: c[k] for k in ("id", "nome", "tier", "persona", "aeroportoBase", "clvProjetado",
                              "scoreValor", "riscoEvasao")} | {"proximaAcao": c["proximaAcao"]["titulo"]}


def _rotular_recomendacao(
    acao: dict, policies_verified: bool = False, policy_context: str | None = None
) -> dict:
    """Keep every surfaced recommendation explicitly demonstrative."""
    status = (
        "Contexto de política marcado como verificado; elegibilidade individual "
        "não confirmada."
        if policies_verified
        else "Contexto de política não verificado; sugestão demonstrativa."
    )
    result = acao.copy()
    title = result.get("titulo", "Recomendação")
    if "política" not in title.lower() and "simulação" not in title.lower():
        result["titulo"] = (
            f"{title} — política verificada; validar elegibilidade"
            if policies_verified
            else f"{title} — simulação; política não verificada"
        )
    message = result.get("mensagem", "")
    if _DEMONSTRATION_NOTICE not in message:
        result["mensagem"] = f"{_DEMONSTRATION_NOTICE}\n\n{message}".strip()
    justification = result.get("justificativa", [])
    if status not in justification:
        result["justificativa"] = [*justification, status]
    rules = result.get("regrasFidelidade", [])
    surfaced_rules = [status]
    if policy_context:
        surfaced_rules.append(policy_context)
    result["regrasFidelidade"] = list(dict.fromkeys([*surfaced_rules, *rules]))
    return result


class CrmService:
    @staticmethod
    def carregar_clientes() -> list[dict]:
        df = DataLakeService.read_gold()
        if df.empty:
            return []
        if "churn_score" not in df.columns:
            scores, _ = DataLakeService.score_gold(df)
            df["churn_score"] = scores
        return [_linha_para_cliente(r) for r in df.itertuples()]

    @classmethod
    def listar(cls, persona: str | None = None, tier: str | None = None) -> list[dict]:
        return [_resumo(c) for c in cls._filtrar(cls.carregar_clientes(), persona, tier)]

    @staticmethod
    def _filtrar(clientes, persona=None, tier=None):
        return [c for c in clientes if (not persona or c["persona"] == persona) and (not tier or c["tier"] == tier)]

    @classmethod
    def obter(cls, cliente_id: str) -> dict | None:
        return next((c for c in cls.carregar_clientes() if c["id"] == cliente_id), None)

    @classmethod
    def resumo_dashboard(cls, persona: str | None = None, tier: str | None = None) -> dict:
        todos = cls._filtrar(cls.carregar_clientes(), None, tier)
        cs = [c for c in todos if not persona or c["persona"] == persona]
        n = len(cs)
        media = lambda xs: (sum(xs) / len(xs)) if xs else 0
        scored = [c for c in cs if c["riscoEvasao"] is not None]
        risco = [c for c in scored if c["riscoEvasao"] >= RISCO_ALTO]
        atritos = {}
        return {
            "dataReferencia": DATA_REFERENCIA,
            "totalClientes": n,
            "clientesAltoValor": sum(c["scoreValor"] >= SCORE_ALTO_VALOR for c in cs),
            "clvMedio": media([c["clvProjetado"] for c in cs]),
            "receitaEmRisco": sum(c["clvProjetado"] for c in risco),
            "percentualRiscoAlto": len(risco) / len(scored) if scored else None,
            "sentimentoMedio": media([c["sentimentoScore"] for c in cs]),
            "receitaMensal": [
                {"mes": m, "voos": sum(c["historico"][i]["voos"] for c in cs),
                 "receita": sum(c["historico"][i]["receita"] for c in cs)}
                for i, m in enumerate(MESES)
            ],
            "porPersona": [
                {"persona": p, "clientes": len(g), "clvTotal": sum(c["clvProjetado"] for c in g),
                 "riscoMedio": (
                     media([c["riscoEvasao"] for c in g if c["riscoEvasao"] is not None])
                     if any(c["riscoEvasao"] is not None for c in g)
                     else None
                 )}
                for p in PERSONAS for g in [[c for c in todos if c["persona"] == p]]
            ],
            "porTier": [{"tier": t, "clientes": sum(c["tier"] == t for c in cs)} for t in TIERS],
            "atritos": [{"tema": k, "mencoes": v} for k, v in atritos.items()],
            "matriz": [_resumo(c) for c in cs],
            "prioritarios": [_resumo(c) for c in sorted(
                cs,
                key=lambda c: c["clvProjetado"] * (c["riscoEvasao"] or 0),
                reverse=True,
            )[:10]],
        }


def gerar_recomendacao(cliente: dict) -> dict:
    """Run the graph workflow, optionally personalize text, and keep fallback visible."""
    base = cliente["proximaAcao"]
    try:
        final = invoke_agent_workflow({
            "client_identifier": cliente["id"],
            "churn_score": cliente["_churn_score"],
            "frequency": cliente["voos12m"],
            "total_spend": cliente["receita12m"],
            "flight_incidents": cliente["_flight_incidents"],
            "incident_type": cliente["_incident_type"],
            "tier": cliente["tier"],
            "value_at_risk": 0.0,
            "graph_rag_context": {},
            "decision": {},
            "audit_status": "",
        })
    except Exception as error:
        logger.error(
            "Deterministic recommendation workflow failed; type=%s; using rules fallback.",
            type(error).__name__,
        )
        return _rotular_recomendacao(base | {"origem": "regras"})

    decision = final["decision"]
    graph_context = final["graph_rag_context"]
    regras = [
        graph_context["policy_context"],
        *graph_context.get("graph_relations", []),
    ]
    deterministic = base | {
        "tipo": decision["action_code"],
        "titulo": decision["strategy"],
        "justificativa": [decision["reasoning"], *decision["evidence"]],
        "canal": "Telefone" if decision["action_code"] == "recuperacao-servico" else "App",
        "mensagem": decision["proposal"]["benefit"],
        "regrasFidelidade": regras,
        "confianca": None,
        "origem": "regras",
        "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
    }

    from ai.llm.contracts import LLMProviderError
    from app.services.llm_provider_factory import create_llm_service
    try:
        output = create_llm_service(settings).recommend(final)
    except LLMProviderError as error:
        logger.warning(
            "LLM recommendation unavailable; reason=%s; "
            "deterministic rules fallback used.",
            error.reason,
        )
        return _rotular_recomendacao(
            deterministic | {"origem": "llm-indisponivel"},
            graph_context.get("policies_verified") is True,
            graph_context.get("policy_context"),
        )

    if output is None:
        return _rotular_recomendacao(
            deterministic,
            graph_context.get("policies_verified") is True,
            graph_context.get("policy_context"),
        )

    llm_recommendation = deterministic | {
        "justificativa": [
            output.reasoning,
            *output.evidence,
            *decision["evidence"],
        ],
        "canal": output.channel,
        "mensagem": output.message,
        "regrasFidelidade": regras,
        "confianca": None,
        "origem": "llm",
    }
    return _rotular_recomendacao(
        llm_recommendation,
        graph_context.get("policies_verified") is True,
        graph_context.get("policy_context"),
    )
