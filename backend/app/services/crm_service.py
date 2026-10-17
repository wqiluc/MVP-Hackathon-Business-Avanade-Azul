import pandas as pd
from app.services.datalake_service import DataLakeService

DATA_REFERENCIA = "2026-09-30"
MESES = ["out/25", "nov/25", "dez/25", "jan/26", "fev/26", "mar/26",
         "abr/26", "mai/26", "jun/26", "jul/26", "ago/26", "set/26"]
TIERS = ["Básico", "Topázio", "Safira", "Diamante"]
PERSONAS = ["executivo-frequente", "lazer-premium", "regional-conectado", "potencial-ascensao"]
RISCO_ALTO = 0.5
SCORE_ALTO_VALOR = 70

_TIER_MAP = {"BASICO": "Básico", "BÁSICO": "Básico", "TOPAZIO": "Topázio", "TOPÁZIO": "Topázio",
             "SAFIRA": "Safira", "DIAMANTE": "Diamante"}


def _tier(valor) -> str:
    return _TIER_MAP.get(str(valor).strip().upper(), "Básico")


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


def _acao_regras(risco: float, tier: str, incidentes: int) -> dict:
    if incidentes >= 2:
        tipo, titulo, canal = "recuperacao-servico", "Recuperação de serviço com voucher e contato ativo", "Telefone"
    elif risco >= RISCO_ALTO:
        tipo, titulo, canal = "bonus-pontos", "Bônus de pontos para reativação", "E-mail"
    elif tier in ("Safira", "Diamante"):
        tipo, titulo, canal = "upgrade", "Upgrade de cortesia na próxima viagem", "App"
    else:
        tipo, titulo, canal = "comunicacao", "Comunicação de relacionamento personalizada", "E-mail"
    return {
        "tipo": tipo, "titulo": titulo, "canal": canal,
        "justificativa": [f"Risco de evasão estimado em {risco:.0%}", f"Categoria {tier}"],
        "mensagem": "Olá! Preparamos uma condição especial para você voar mais com a Azul.",
        "regrasFidelidade": [], "confianca": 0.7, "origem": "simulacao",
        "impactoEstimado": {"reducaoRiscoPp": round(min(risco * 40, 25), 1), "receitaProtegida": 0.0},
    }


def _linha_para_cliente(r) -> dict:
    tier = _tier(r.tier)
    risco = float(r.churn_score)
    receita = float(r.total_spend)
    clv = round(receita * 2 * (1 - risco * 0.5), 2)
    score = round(min(100, 100 * (0.4 * min(receita / 60000, 1) + 0.35 * min(r.frequency / 24, 1)
                                  + 0.25 * max(0, 1 - r.recency_days / 180))), 1)
    persona = _persona(type("R", (), {"tier": tier, "frequency": r.frequency, "avg_ticket": float(r.avg_ticket or 0)}))
    pesos = [1 / len(MESES)] * len(MESES)
    acao = _acao_regras(risco, tier, int(r.flight_incidents))
    acao["impactoEstimado"]["receitaProtegida"] = round(clv * risco, 2)
    return {
        "id": r.client_identifier, "nome": r.client_identifier, "tier": tier, "persona": persona,
        "aeroportoBase": "—", "cidadeBase": "—", "membroDesde": DATA_REFERENCIA,
        "consentimentoMarketing": True,
        "clvProjetado": clv, "scoreValor": score, "riscoEvasao": round(risco, 3),
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


class CrmService:
    @staticmethod
    def carregar_clientes() -> list[dict]:
        df = DataLakeService.read_gold()
        if df.empty:
            return []
        if "churn_score" not in df.columns:
            from app.services.inference_service import predict_churn
            df["churn_score"] = predict_churn(df)
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
        risco = [c for c in cs if c["riscoEvasao"] >= RISCO_ALTO]
        atritos = {}
        return {
            "dataReferencia": DATA_REFERENCIA,
            "totalClientes": n,
            "clientesAltoValor": sum(c["scoreValor"] >= SCORE_ALTO_VALOR for c in cs),
            "clvMedio": media([c["clvProjetado"] for c in cs]),
            "receitaEmRisco": sum(c["clvProjetado"] for c in risco),
            "percentualRiscoAlto": len(risco) / n if n else 0,
            "sentimentoMedio": media([c["sentimentoScore"] for c in cs]),
            "receitaMensal": [
                {"mes": m, "voos": sum(c["historico"][i]["voos"] for c in cs),
                 "receita": sum(c["historico"][i]["receita"] for c in cs)}
                for i, m in enumerate(MESES)
            ],
            "porPersona": [
                {"persona": p, "clientes": len(g), "clvTotal": sum(c["clvProjetado"] for c in g),
                 "riscoMedio": media([c["riscoEvasao"] for c in g])}
                for p in PERSONAS for g in [[c for c in todos if c["persona"] == p]]
            ],
            "porTier": [{"tier": t, "clientes": sum(c["tier"] == t for c in cs)} for t in TIERS],
            "atritos": [{"tema": k, "mencoes": v} for k, v in atritos.items()],
            "matriz": [_resumo(c) for c in cs],
            "prioritarios": [_resumo(c) for c in sorted(
                cs, key=lambda c: c["clvProjetado"] * c["riscoEvasao"], reverse=True)[:10]],
        }


def gerar_recomendacao(cliente: dict) -> dict:
    """Aciona os agentes (GraphRAG + decisão + auditoria) e converte para ProximaAcao do front."""
    base = cliente["proximaAcao"]
    try:
        from app.api.v1.clients import agent_orchestrator
        final = agent_orchestrator.invoke({
            "client_identifier": cliente["id"], "frequency": cliente["voos12m"],
            "total_spend": cliente["receita12m"], "incidents": round(max(0, 1 - cliente["sentimentoScore"]) * 2),
            "incident_type": "Downgrade Involuntário", "tier": "", "churn_risk": 0.0, "value_at_risk": 0.0,
            "graph_rag_context": {}, "decision_reasoning": "", "action_proposal": {}, "audit_status": "",
        })
    except Exception:
        return base
    prop = final["action_proposal"]
    regras = final["graph_rag_context"]
    return base | {
        "titulo": prop.get("strategy", base["titulo"]),
        "justificativa": [final["decision_reasoning"], f"Auditoria: {final['audit_status']}"],
        "mensagem": f"{prop.get('benefit', '')} + voucher de R$ {prop.get('voucher_value', 0):.2f}".strip(" +"),
        "regrasFidelidade": [str(v) for v in regras.values()] if isinstance(regras, dict) else [],
        "confianca": 0.85, "origem": "ia-generativa",
    }
