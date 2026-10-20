"""Enriquece a base de clientes sintéticos e trata as camadas Bronze, Silver e Gold.

Parte de clientes_sinteticos_snowflake_10000.csv (os 2000 clientes da base
original, CLI-100000 a CLI-101999, mais 8000 gerados a partir deles) e usa a
estrutura já existente do projeto: pastas datalake/bronze, silver e gold,
conexão Snowflake de database.py e o banco AZUL_DATA_LAKE.

Uso:
    python pipeline_datalake.py gerar  [--total 10000]  # Bronze (total > base expande por bootstrap)
    python pipeline_datalake.py tratar                  # Silver + Gold (local)
    python pipeline_datalake.py ddl                     # regrava sql/06_clientes_azul_expandido.sql
    python pipeline_datalake.py enviar                  # Bronze/Silver/Gold -> Snowflake
    python pipeline_datalake.py trazer                  # Snowflake GOLD -> datalake/gold (front-end)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_BASE = BASE_DIR / "clientes_sinteticos_snowflake_10000.csv"
DATALAKE = BASE_DIR / "datalake"
BRONZE_CSV = DATALAKE / "bronze" / "clientes_azul_bronze.csv"
SILVER_CSV = DATALAKE / "silver" / "clientes_azul_silver.csv"
GOLD_CSV = DATALAKE / "gold" / "clientes_azul_gold.csv"
RELATORIO_SILVER = DATALAKE / "silver" / "relatorio_qualidade_silver.json"
RESUMO_GOLD = DATALAKE / "gold" / "resumo_gold.json"
DDL_SQL = BASE_DIR / "sql" / "06_clientes_azul_expandido.sql"

DATA_REFERENCIA = date(2026, 10, 20)
SEED = 42
TOTAL_PADRAO = 10_000

# --- Calibração por fontes públicas (ver datalake/README.md) ---
TARIFA_MEDIA_ANAC = 648.0  # ANAC, Anuário 2025: tarifa média doméstica (R$)
# Azul Fidelidade 2026, ano-calendário (fonte pública; validar no site oficial)
REGRAS_CATEGORIA = {  # categoria: (trechos, pontos qualificáveis, regra, gasto alternativo)
    "Topazio": (6, 6_000, "OU", None),
    "Safira": (10, 10_000, "OU", None),
    "Diamante": (12, 12_000, "E", 25_000),
}
ORDEM_CATEGORIA = ["Basico", "Topazio", "Safira", "Diamante"]
CATEGORIA_POR_PRODUTO = {"GOLD": "Topazio", "PLATINUM": "Safira", "INFINITE": "Diamante",
                         "CLUBE_10000": "Safira", "CLUBE_20000": "Diamante"}

COLUNAS_ORIGINAIS = ["CUSTOMER_ID", "NOME", "EMAIL", "ESTADO", "CATEGORIA_TIER",
                     "PONTOS_ACUMULADOS", "VOOS_ANO", "RISCO_CHURN", "DATA_CADASTRO"]
COLUNAS_NOVAS = [
    "AEROPORTO_BASE", "ROTA_FAVORITA", "MOTIVO_VIAGEM", "TARIFA_PREFERIDA", "USA_ESPACO_AZUL",
    "VIAJA_INTERNACIONAL", "ANTECEDENCIA_MEDIA_DIAS", "DIA_SEMANA_PREFERIDO", "ACOMPANHANTES_MEDIA",
    "CANAL_COMPRA", "VOOS_ANO_ANTERIOR", "DATA_ULTIMO_VOO", "GASTO_TOTAL_12M", "RESGATES_PONTOS_12M",
    "PONTOS_A_EXPIRAR_90D", "CARTAO_AZUL_ITAU", "CLUBE_AZUL", "ATRASOS_SOFRIDOS_12M",
    "RECLAMACOES_12M", "NPS_ULTIMO", "COMENTARIO_ULTIMO_CONTATO", "OPT_IN_MARKETING",
    "CANAL_CONTATO_PREFERIDO", "DATA_ATUALIZACAO",
]
COLUNAS_BRONZE = COLUNAS_ORIGINAIS + COLUNAS_NOVAS + ["ORIGEM_REGISTRO", "DATA_INGESTAO"]

TIPOS_SILVER = {
    "CUSTOMER_ID": "VARCHAR(20)", "NOME": "VARCHAR(150)", "EMAIL": "VARCHAR(150)",
    "EMAIL_VALIDO": "BOOLEAN", "EMAIL_DUPLICADO": "BOOLEAN", "ESTADO": "VARCHAR(2)",
    "CATEGORIA_TIER": "VARCHAR(20)", "PONTOS_ACUMULADOS": "NUMBER(10,0)", "VOOS_ANO": "NUMBER(5,0)",
    "RISCO_CHURN": "VARCHAR(10)", "DATA_CADASTRO": "DATE", "AEROPORTO_BASE": "VARCHAR(3)",
    "ROTA_FAVORITA": "VARCHAR(7)", "MOTIVO_VIAGEM": "VARCHAR(20)", "TARIFA_PREFERIDA": "VARCHAR(20)",
    "USA_ESPACO_AZUL": "BOOLEAN", "VIAJA_INTERNACIONAL": "BOOLEAN", "ANTECEDENCIA_MEDIA_DIAS": "NUMBER(5,0)",
    "DIA_SEMANA_PREFERIDO": "VARCHAR(3)", "ACOMPANHANTES_MEDIA": "NUMBER(4,1)", "CANAL_COMPRA": "VARCHAR(20)",
    "VOOS_ANO_ANTERIOR": "NUMBER(5,0)", "DATA_ULTIMO_VOO": "DATE", "GASTO_TOTAL_12M": "NUMBER(12,2)",
    "RESGATES_PONTOS_12M": "NUMBER(5,0)", "PONTOS_A_EXPIRAR_90D": "NUMBER(10,0)",
    "CARTAO_AZUL_ITAU": "VARCHAR(10)", "CLUBE_AZUL": "VARCHAR(15)", "ATRASOS_SOFRIDOS_12M": "NUMBER(5,0)",
    "RECLAMACOES_12M": "NUMBER(5,0)", "NPS_ULTIMO": "NUMBER(2,0)", "COMENTARIO_ULTIMO_CONTATO": "VARCHAR(500)",
    "SENTIMENTO_SCORE": "FLOAT", "SENTIMENTO_ULTIMO_CONTATO": "VARCHAR(10)", "OPT_IN_MARKETING": "BOOLEAN",
    "CANAL_CONTATO_PREFERIDO": "VARCHAR(10)", "DATA_ATUALIZACAO": "TIMESTAMP_NTZ",
    "ORIGEM_REGISTRO": "VARCHAR(60)",
}

TIPOS_GOLD = {
    # identificação (NOME/EMAIL só para o operador de CRM no front-end, nunca para a IA)
    "CUSTOMER_ID": "VARCHAR(20)", "NOME": "VARCHAR(150)", "EMAIL": "VARCHAR(150)", "ESTADO": "VARCHAR(2)",
    "AEROPORTO_BASE": "VARCHAR(3)", "CATEGORIA_TIER": "VARCHAR(20)", "MESES_RELACIONAMENTO": "NUMBER(5,0)",
    # valor (RFM + CLV)
    "VOOS_ANO": "NUMBER(5,0)", "VOOS_ANO_ANTERIOR": "NUMBER(5,0)", "TENDENCIA_VOOS": "FLOAT",
    "GASTO_TOTAL_12M": "NUMBER(12,2)", "TICKET_MEDIO": "NUMBER(10,2)", "DIAS_DESDE_ULTIMO_VOO": "NUMBER(5,0)",
    "SCORE_VALOR": "NUMBER(5,1)", "CLV_ESTIMADO_36M": "NUMBER(12,2)", "SEGMENTO_VALOR": "VARCHAR(10)",
    "ALTO_VALOR": "BOOLEAN",
    # risco de evasão com explicabilidade
    "RISCO_CHURN": "VARCHAR(10)", "PROB_CHURN_90D": "FLOAT", "FATORES_RISCO": "VARCHAR(500)",
    # persona e padrão de viagem
    "PERSONA": "VARCHAR(30)", "PERSONA_MOTIVO": "VARCHAR(200)", "MOTIVO_VIAGEM": "VARCHAR(20)",
    "ROTA_FAVORITA": "VARCHAR(7)", "TARIFA_PREFERIDA": "VARCHAR(20)", "USA_ESPACO_AZUL": "BOOLEAN",
    "VIAJA_INTERNACIONAL": "BOOLEAN", "ANTECEDENCIA_MEDIA_DIAS": "NUMBER(5,0)",
    "DIA_SEMANA_PREFERIDO": "VARCHAR(3)", "ACOMPANHANTES_MEDIA": "NUMBER(4,1)", "CANAL_COMPRA": "VARCHAR(20)",
    # previsão da próxima viagem
    "PROXIMA_VIAGEM_DATA": "DATE", "PROXIMA_VIAGEM_JANELA_COMPRA": "DATE", "PROXIMA_VIAGEM_ROTA": "VARCHAR(7)",
    "PROXIMA_VIAGEM_TARIFA": "VARCHAR(20)", "PROXIMA_VIAGEM_PAGAMENTO": "VARCHAR(10)",
    "PROXIMA_VIAGEM_CONFIANCA": "VARCHAR(15)",
    # fidelidade
    "PONTOS_ACUMULADOS": "NUMBER(10,0)", "PONTOS_A_EXPIRAR_90D": "NUMBER(10,0)", "RESGATES_PONTOS_12M": "NUMBER(5,0)",
    "CARTAO_AZUL_ITAU": "VARCHAR(10)", "CLUBE_AZUL": "VARCHAR(15)", "CATEGORIA_PROJETADA": "VARCHAR(20)",
    "RISCO_REBAIXAMENTO": "BOOLEAN", "PROXIMA_CATEGORIA": "VARCHAR(20)", "FALTAM_TRECHOS_PROXIMA": "NUMBER(5,0)",
    # experiência
    "ATRASOS_SOFRIDOS_12M": "NUMBER(5,0)", "RECLAMACOES_12M": "NUMBER(5,0)", "NPS_ULTIMO": "NUMBER(2,0)",
    "SENTIMENTO_ULTIMO_CONTATO": "VARCHAR(10)", "COMENTARIO_ULTIMO_CONTATO": "VARCHAR(500)",
    # próxima melhor ação
    "ACAO_RECOMENDADA": "VARCHAR(30)", "ACAO_DESCRICAO": "VARCHAR(300)", "CANAL_CONTATO": "VARCHAR(25)",
    "PRIORIDADE_CRM": "NUMBER(5,1)", "DATA_REFERENCIA": "DATE",
}

# Campos da Gold que vão para o agente de IA: sem nome, e-mail ou texto livre (LGPD).
COLUNAS_CONTEXTO_IA = [c for c in TIPOS_GOLD if c not in ("NOME", "EMAIL", "COMENTARIO_ULTIMO_CONTATO")]

CAMADAS_SNOWFLAKE = [  # (schema, tabela, arquivo)
    ("BRONZE", "CLIENTES_AZUL_RAW", BRONZE_CSV),
    ("SILVER", "CLIENTES_AZUL", SILVER_CSV),
    ("GOLD", "CLIENTES_AZUL", GOLD_CSV),
]

# ---------------------------------------------------------------- perfis de geração
AEROPORTOS_UF = {
    "SP": (["VCP", "GRU", "CGH"], [0.55, 0.25, 0.20]), "PE": (["REC"], [1.0]),
    "RJ": (["SDU", "GIG"], [0.6, 0.4]), "MG": (["CNF"], [1.0]), "BA": (["SSA"], [1.0]),
    "PR": (["CWB"], [1.0]), "RS": (["POA"], [1.0]), "CE": (["FOR"], [1.0]),
    "GO": (["GYN"], [1.0]), "SC": (["FLN"], [1.0]),
}
UF_DO_AEROPORTO = {
    "VCP": "SP", "GRU": "SP", "CGH": "SP", "CNF": "MG", "REC": "PE", "SDU": "RJ", "GIG": "RJ",
    "BSB": "DF", "POA": "RS", "CWB": "PR", "SSA": "BA", "FOR": "CE", "NAT": "RN", "MCZ": "AL",
    "FEN": "PE", "BPS": "BA", "FLN": "SC", "IGU": "PR", "JPA": "PB", "GYN": "GO",
}
DESTINOS = {
    "NEGOCIOS": ["VCP", "CNF", "REC", "SDU", "CGH", "BSB", "POA", "CWB", "SSA", "GRU"],
    "LAZER": ["REC", "SSA", "FOR", "NAT", "MCZ", "FEN", "BPS", "FLN", "IGU", "JPA"],
}
HUB_INTERNACIONAL = {"SP": "VCP", "MG": "CNF", "PE": "REC"}  # demais estados conectam via VCP
DESTINOS_INTERNACIONAIS = ["MCO", "FLL", "LIS"]

PERFIS = {  # comportamento por perfil latente (não sai na base; a Gold infere a persona dos dados)
    "EXECUTIVO": dict(motivo={"CORPORATIVO": .8, "MISTO": .2}, tarifa={"MAIS_AZUL": .6, "AZUL": .3, "BUSINESS": .1},
                      espaco=.45, intl=.15, antecedencia=7, dias=["SEG", "TER", "QUI"], acomp=.1,
                      canal={"CORPORATIVO": .5, "APP": .35, "SITE": .15}, resgate=.05, clube=.08, destinos="NEGOCIOS"),
    "LAZER": dict(motivo={"LAZER": .85, "MISTO": .15}, tarifa={"AZUL": .55, "MAIS_AZUL": .35, "BUSINESS": .1},
                  espaco=.15, intl=.35, antecedencia=45, dias=["QUI", "SEX", "SAB"], acomp=1.6,
                  canal={"SITE": .4, "APP": .3, "AGENCIA": .3}, resgate=.15, clube=.1, destinos="LAZER"),
    "CACADOR": dict(motivo={"LAZER": .7, "MISTO": .3}, tarifa={"AZUL": .9, "MAIS_AZUL": .1},
                    espaco=.05, intl=.15, antecedencia=35, dias=["TER", "QUA", "SAB"], acomp=.6,
                    canal={"APP": .65, "SITE": .35}, resgate=.55, clube=.5, destinos="LAZER"),
    "OCASIONAL": dict(motivo={"LAZER": .8, "MISTO": .2}, tarifa={"AZUL": .85, "MAIS_AZUL": .15},
                      espaco=.05, intl=.03, antecedencia=25, dias=["SEX", "SAB", "DOM"], acomp=.9,
                      canal={"SITE": .45, "APP": .3, "AGENCIA": .25}, resgate=.05, clube=.02, destinos="LAZER"),
}
PESOS_PERFIL_POR_TIER = {  # EXECUTIVO, LAZER, CACADOR (OCASIONAL depende da frequência)
    "Diamante": [.72, .18, .10], "Safira": [.50, .30, .20], "Topazio": [.25, .45, .30], "Basico": [.10, .55, .35],
}
CARTAO_POR_TIER = {  # NENHUM, GOLD, PLATINUM, INFINITE (o cartão nunca dá categoria acima da atual)
    "Basico": [1.0, 0, 0, 0], "Topazio": [.65, .35, 0, 0], "Safira": [.45, .25, .30, 0], "Diamante": [.30, .10, .30, .30],
}
CLUBES_POR_TIER = {
    "Basico": [1_000, 2_000, 5_000], "Topazio": [1_000, 2_000, 5_000],
    "Safira": [1_000, 2_000, 5_000, 10_000], "Diamante": [2_000, 5_000, 10_000, 20_000],
}
PROPENSAO_CHURN = {"Alto": (.35, .70), "Medio": (.12, .30), "Baixo": (.02, .10)}
MULT_TARIFA = {"AZUL": 1.0, "MAIS_AZUL": 1.35, "BUSINESS": 3.0}

COMENTARIOS = {
    "NEGATIVO": {
        "ATRASO": ["Voo {rota} atrasou de novo e ninguém deu informação. Péssimo.",
                   "Mais um atraso na rota {rota}, perdi um compromisso. Descaso total."],
        "BAGAGEM": ["Minha mala foi extraviada no voo {rota} e ainda estou sem retorno."],
        "REEMBOLSO": ["Pedi reembolso há semanas e nada. Demora absurda."],
        "PONTOS": ["Meus pontos sumiram do extrato e o atendimento não resolveu."],
        "ATENDIMENTO": ["Atendimento ruim no balcão, atendente grosseiro."],
        "APP": ["O app travou no check-in e tive que ir ao balcão. Horrível."],
    },
    "NEUTRO": ["Viagem dentro do esperado na rota {rota}.", "Voo {rota} normal, sem novidades."],
    "POSITIVO": ["Voo {rota} pontual e tripulação muito atenciosa. Recomendo!",
                 "Espaço Azul vale muito a pena, viagem confortável.",
                 "Ótimo atendimento, resolveram meu pedido rápido.",
                 "Adorei o serviço de bordo, excelente experiência."],
}

LEXICO_POSITIVO = {"pontual", "atenciosa", "atencioso", "recomendo", "confortavel", "otimo", "excelente",
                   "rapido", "adorei", "resolveram", "vale", "bom", "boa", "perfeito", "parabens"}
LEXICO_NEGATIVO = {"atrasou", "atraso", "pessimo", "descaso", "extraviada", "demora", "absurda", "sumiram",
                   "ruim", "grosseiro", "travou", "horrivel", "cancelaram", "prejuizo", "resolveu"}
NEGADORES = {"nao", "nunca", "nem"}

RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
RE_TELEFONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")
RE_EMAIL_VALIDO = re.compile(r"^[\w.+-]+@[\w-]+\.[a-z]{2,}$")


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _escolher(rng: np.random.Generator, pesos: dict[str, float]) -> str:
    chaves = list(pesos)
    p = np.array([pesos[k] for k in chaves], dtype=float)
    return chaves[rng.choice(len(chaves), p=p / p.sum())]


# ================================================================ BRONZE
def expandir_base(original: pd.DataFrame, total: int, rng: np.random.Generator, seed: int = SEED) -> pd.DataFrame:
    """Completa a base até ``total`` clientes por bootstrap dos clientes existentes.

    Os clientes existentes são mantidos; os novos herdam tier, estado e risco de um
    cliente sorteado, com variação em pontos, voos e data de cadastro.
    """
    base = original[COLUNAS_ORIGINAIS].copy()
    base["ORIGEM_REGISTRO"] = CSV_BASE.name

    novos = max(0, total - len(base))
    if novos:
        modelo = base.sample(n=novos, replace=True, random_state=seed).reset_index(drop=True)
        primeiros = original["NOME"].str.split().str[0].unique()
        sobrenomes = original["NOME"].str.split().str[-1].unique()
        inicio_id = int(original["CUSTOMER_ID"].str[4:].astype(int).max()) + 1
        nomes, emails = [], []
        for i in range(novos):
            p, s = rng.choice(primeiros), rng.choice(sobrenomes)
            nomes.append(f"{p} {s}")
            emails.append(f"{_sem_acento(p).lower()}.{_sem_acento(s).lower()}.{inicio_id + i}@emailmock.com")
        cadastro = pd.to_datetime(modelo["DATA_CADASTRO"]) + pd.to_timedelta(rng.integers(-120, 121, novos), unit="D")
        cadastro = cadastro.clip(upper=pd.Timestamp(DATA_REFERENCIA) - pd.Timedelta(days=30))
        modelo = modelo.assign(
            CUSTOMER_ID=[f"CLI-{inicio_id + i}" for i in range(novos)],
            NOME=nomes,
            EMAIL=emails,
            PONTOS_ACUMULADOS=(modelo["PONTOS_ACUMULADOS"] * rng.uniform(0.85, 1.15, novos)).round().astype(int),
            VOOS_ANO=np.maximum(0, np.round(modelo["VOOS_ANO"] * rng.uniform(0.8, 1.2, novos))).astype(int),
            DATA_CADASTRO=cadastro.dt.strftime("%Y-%m-%d"),
            ORIGEM_REGISTRO="expansao_sintetica_bootstrap",
        )
        base = pd.concat([base, modelo], ignore_index=True)
    return base


def gerar_bronze(clientes: pd.DataFrame, total: int = TOTAL_PADRAO, seed: int = SEED) -> pd.DataFrame:
    """Enriquece a base de clientes com comportamento de viagem e simula a ingestão bruta."""
    rng = np.random.default_rng(seed)
    base = expandir_base(clientes, total, rng, seed)

    comportamento = pd.DataFrame([_gerar_comportamento(linha, rng) for linha in base.itertuples(index=False)])
    comportamento["NPS_ULTIMO"] = comportamento["NPS_ULTIMO"].astype("Int64")
    bronze = pd.concat([base.reset_index(drop=True), comportamento], axis=1)
    bronze["DATA_INGESTAO"] = f"{DATA_REFERENCIA.isoformat()}T03:00:00"
    bronze = _aplicar_ruido_de_ingestao(bronze[COLUNAS_BRONZE], rng)
    return bronze.astype(str).replace({"nan": "", "None": "", "<NA>": ""})


def _gerar_comportamento(c, rng: np.random.Generator) -> dict:
    tier, voos = c.CATEGORIA_TIER, int(c.VOOS_ANO)
    if voos <= 2 and rng.random() < 0.8:
        perfil_nome = "OCASIONAL"
    else:
        perfil_nome = ["EXECUTIVO", "LAZER", "CACADOR"][rng.choice(3, p=PESOS_PERFIL_POR_TIER[tier])]
    perfil = PERFIS[perfil_nome]
    p_churn = rng.uniform(*PROPENSAO_CHURN[c.RISCO_CHURN])

    aeroportos, pesos = AEROPORTOS_UF[c.ESTADO]
    base = aeroportos[rng.choice(len(aeroportos), p=pesos)]
    intl = rng.random() < perfil["intl"]
    if intl and rng.random() < 0.5:
        rota = f"{HUB_INTERNACIONAL.get(c.ESTADO, 'VCP')}-{rng.choice(DESTINOS_INTERNACIONAIS)}"
    else:
        opcoes = [d for d in DESTINOS[perfil["destinos"]] if UF_DO_AEROPORTO[d] != c.ESTADO]
        rota = f"{base}-{rng.choice(opcoes)}"
    tarifa = _escolher(rng, perfil["tarifa"])
    if tarifa == "BUSINESS" and not intl:
        tarifa = "MAIS_AZUL"

    # frequência, recência e tendência coerentes com o risco de evasão
    cadastro = date.fromisoformat(c.DATA_CADASTRO)
    dias_membro = (DATA_REFERENCIA - cadastro).days
    fator_anterior = {"Alto": (1.3, 2.2), "Medio": (0.9, 1.4), "Baixo": (0.75, 1.15)}[c.RISCO_CHURN]
    voos_anterior = round(voos * rng.uniform(*fator_anterior)) if voos else int(rng.poisson(2 if c.RISCO_CHURN == "Alto" else 0.5))
    voos_anterior = round(voos_anterior * min(1.0, max(0, dias_membro - 365) / 365))
    if voos:
        intervalo = 365 / voos
        fator_rec = {"Baixo": (0.0, 1.0), "Medio": (0.3, 1.5), "Alto": (1.0, 2.5)}[c.RISCO_CHURN]
        dias_ultimo = int(np.clip(intervalo * rng.uniform(*fator_rec), 1, min(365, dias_membro)))
    elif voos_anterior:
        dias_ultimo = int(rng.integers(366, max(367, min(730, dias_membro))))
    else:
        dias_ultimo = None
    ultimo_voo = (DATA_REFERENCIA - timedelta(days=dias_ultimo)).isoformat() if dias_ultimo else None

    resgates = int(rng.binomial(voos, perfil["resgate"])) if voos else 0
    acomp = round(max(0.0, rng.normal(perfil["acomp"], 0.4)), 1)
    # tarifa ANAC ajustada por família, compra em cima da hora (executivo) e rota internacional
    ticket = (TARIFA_MEDIA_ANAC * MULT_TARIFA[tarifa] * (1.15 if perfil_nome == "EXECUTIVO" else 1.0)
              * (1.6 if rota.split("-")[1] in DESTINOS_INTERNACIONAIS else 1.0) * rng.lognormal(0, 0.2))
    gasto = round((voos - resgates) * ticket, 2)

    pontos = int(c.PONTOS_ACUMULADOS)
    fracao_expirar = {"Alto": (0.10, 0.40), "Medio": (0.0, 0.20), "Baixo": (0.0, 0.08)}[c.RISCO_CHURN]
    a_expirar = int(round(pontos * rng.uniform(*fracao_expirar), -1))

    cartao = ["NENHUM", "GOLD", "PLATINUM", "INFINITE"][rng.choice(4, p=CARTAO_POR_TIER[tier])]
    clube = f"CLUBE_{rng.choice(CLUBES_POR_TIER[tier])}" if rng.random() < perfil["clube"] else "NENHUM"

    atrasos = int(rng.poisson(voos * (0.07 + 0.15 * p_churn)))
    reclamacoes = int(rng.poisson(0.05 + atrasos * (0.15 + 0.5 * p_churn) + 0.3 * p_churn))
    nps = None
    if (voos or reclamacoes) and rng.random() < 0.6:
        satisfacao = 1 - p_churn
        nps = int(np.clip(round(rng.normal(9.3 * satisfacao + 0.6 - 1.2 * min(reclamacoes, 3), 1.2)), 0, 10))

    comentario = None
    if reclamacoes:
        tema = "ATRASO" if atrasos else rng.choice(["BAGAGEM", "REEMBOLSO", "PONTOS", "ATENDIMENTO", "APP"])
        comentario = rng.choice(COMENTARIOS["NEGATIVO"][tema])
    elif nps is not None and nps >= 9 and rng.random() < 0.5:
        comentario = rng.choice(COMENTARIOS["POSITIVO"])
    elif nps is not None and nps >= 7 and rng.random() < 0.3:
        comentario = rng.choice(COMENTARIOS["NEUTRO"])
    if comentario:
        comentario = comentario.format(rota=rota)
        if rng.random() < 0.06:  # clientes escrevem dados pessoais no texto livre; a Silver mascara
            comentario += rng.choice([" Meu CPF é 123.456.789-09.", " Me liguem no (11) 98765-4321.",
                                      " Respondam em contato.cliente@emailmock.com."])

    canal_compra = _escolher(rng, perfil["canal"])
    canal_contato = "APP" if canal_compra == "APP" and rng.random() < 0.5 else _escolher(
        rng, {"EMAIL": .5, "WHATSAPP": .4, "APP": .1})
    atualizado = datetime.combine(DATA_REFERENCIA, datetime.min.time()) - timedelta(
        days=int(rng.integers(0, 60)), minutes=int(rng.integers(0, 1440)))

    return {
        "AEROPORTO_BASE": base,
        "ROTA_FAVORITA": rota,
        "MOTIVO_VIAGEM": _escolher(rng, perfil["motivo"]),
        "TARIFA_PREFERIDA": tarifa,
        "USA_ESPACO_AZUL": bool(rng.random() < perfil["espaco"]),
        "VIAJA_INTERNACIONAL": bool(intl),
        "ANTECEDENCIA_MEDIA_DIAS": int(max(0, round(rng.gamma(2.0, perfil["antecedencia"] / 2.0)))),
        "DIA_SEMANA_PREFERIDO": rng.choice(perfil["dias"]),
        "ACOMPANHANTES_MEDIA": acomp,
        "CANAL_COMPRA": canal_compra,
        "VOOS_ANO_ANTERIOR": int(voos_anterior),
        "DATA_ULTIMO_VOO": ultimo_voo,
        "GASTO_TOTAL_12M": gasto,
        "RESGATES_PONTOS_12M": resgates,
        "PONTOS_A_EXPIRAR_90D": a_expirar,
        "CARTAO_AZUL_ITAU": cartao,
        "CLUBE_AZUL": clube,
        "ATRASOS_SOFRIDOS_12M": atrasos,
        "RECLAMACOES_12M": reclamacoes,
        "NPS_ULTIMO": nps,
        "COMENTARIO_ULTIMO_CONTATO": comentario,
        "OPT_IN_MARKETING": bool(rng.random() < 0.8),
        "CANAL_CONTATO_PREFERIDO": canal_contato,
        "DATA_ATUALIZACAO": atualizado.isoformat(timespec="seconds"),
    }


def _aplicar_ruido_de_ingestao(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Simula problemas comuns de ingestão para a Silver tratar (ver relatório de qualidade)."""
    df = df.astype(object).copy()
    n = len(df)
    novos = np.flatnonzero(df["ORIGEM_REGISTRO"] != CSV_BASE.name)

    def amostra(frac: float, linhas: np.ndarray | None = None) -> np.ndarray:
        linhas = np.arange(n) if linhas is None else linhas
        return rng.choice(linhas, size=min(len(linhas), max(1, int(n * frac))), replace=False)

    # snapshot antigo do mesmo cliente (duplicata com data de atualização anterior)
    dup = df.iloc[amostra(0.015)].copy()
    dup["DATA_ATUALIZACAO"] = [
        (datetime.fromisoformat(d) - timedelta(days=int(rng.integers(30, 200)))).isoformat(timespec="seconds")
        for d in dup["DATA_ATUALIZACAO"]
    ]
    dup["PONTOS_ACUMULADOS"] = [int(int(p) * rng.uniform(0.8, 0.98)) for p in dup["PONTOS_ACUMULADOS"]]

    variantes = {"Basico": ["BASICO", "básico", "Básico ", " basico"], "Topazio": ["TOPAZIO", "Topázio", "topazio "],
                 "Safira": ["SAFIRA", " safira"], "Diamante": ["DIAMANTE", "diamante "]}
    for i in amostra(0.04):
        df.at[i, "CATEGORIA_TIER"] = rng.choice(variantes[df.at[i, "CATEGORIA_TIER"]])
    for i in amostra(0.03):
        df.at[i, "ESTADO"] = f" {str(df.at[i, 'ESTADO']).lower()}"
    for i in amostra(0.03):
        df.at[i, "EMAIL"] = str(df.at[i, "EMAIL"]).upper()
    for i in amostra(0.004, novos):  # irreversível: só nos clientes da expansão, nunca nos originais
        df.at[i, "EMAIL"] = str(df.at[i, "EMAIL"]).replace("@", "")
    for i in amostra(0.05):
        df.at[i, "GASTO_TOTAL_12M"] = f"{float(df.at[i, 'GASTO_TOTAL_12M']):.2f}".replace(".", ",")
    for i in amostra(0.005):
        df.at[i, "NPS_ULTIMO"] = rng.choice([11, -1, 99])
    for i in amostra(0.01):
        df.at[i, "TARIFA_PREFERIDA"] = ""
    return pd.concat([df, dup], ignore_index=True)


# ================================================================ SILVER
def tratar_silver(bronze: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Limpa, tipa, deduplica e anonimiza o texto livre. Retorna (silver, relatório)."""
    df = bronze.copy()
    regras: dict[str, int] = {"registros_bronze": len(df)}
    df = df.apply(lambda s: s.str.strip())

    categoria = df["CATEGORIA_TIER"].map(lambda v: _sem_acento(v).capitalize())
    regras["categoria_padronizada"] = int((categoria != df["CATEGORIA_TIER"]).sum())
    df["CATEGORIA_TIER"] = categoria

    estado = df["ESTADO"].str.upper()
    regras["uf_padronizada"] = int((estado != df["ESTADO"]).sum())
    df["ESTADO"] = estado

    email = df["EMAIL"].str.lower()
    regras["email_minusculo"] = int((email != df["EMAIL"]).sum())
    df["EMAIL"] = email
    df["EMAIL_VALIDO"] = df["EMAIL"].str.match(RE_EMAIL_VALIDO)
    regras["email_invalido_sinalizado"] = int((~df["EMAIL_VALIDO"]).sum())

    gasto_virgula = df["GASTO_TOTAL_12M"].str.contains(",", regex=False)
    regras["decimal_com_virgula_corrigido"] = int(gasto_virgula.sum())
    df["GASTO_TOTAL_12M"] = df["GASTO_TOTAL_12M"].str.replace(",", ".", regex=False)

    inteiros = ["PONTOS_ACUMULADOS", "VOOS_ANO", "ANTECEDENCIA_MEDIA_DIAS", "VOOS_ANO_ANTERIOR",
                "RESGATES_PONTOS_12M", "PONTOS_A_EXPIRAR_90D", "ATRASOS_SOFRIDOS_12M", "RECLAMACOES_12M", "NPS_ULTIMO"]
    for col in inteiros:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ["GASTO_TOTAL_12M", "ACOMPANHANTES_MEDIA"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["USA_ESPACO_AZUL", "VIAJA_INTERNACIONAL", "OPT_IN_MARKETING"]:
        df[col] = df[col].str.lower().eq("true")
    nps_fora = df["NPS_ULTIMO"].notna() & ~df["NPS_ULTIMO"].between(0, 10)
    regras["nps_fora_da_faixa_anulado"] = int(nps_fora.sum())
    df.loc[nps_fora, "NPS_ULTIMO"] = pd.NA

    tarifa_vazia = df["TARIFA_PREFERIDA"].eq("")
    regras["tarifa_vazia_imputada_pela_moda_do_motivo"] = int(tarifa_vazia.sum())
    moda = df[~tarifa_vazia].groupby("MOTIVO_VIAGEM")["TARIFA_PREFERIDA"].agg(lambda s: s.mode().iat[0])
    df.loc[tarifa_vazia, "TARIFA_PREFERIDA"] = df.loc[tarifa_vazia, "MOTIVO_VIAGEM"].map(moda)

    antes = len(df)
    df = df.sort_values("DATA_ATUALIZACAO", ascending=False).drop_duplicates("CUSTOMER_ID", keep="first")
    regras["duplicatas_removidas_mantendo_mais_recente"] = antes - len(df)

    df["EMAIL_DUPLICADO"] = df["EMAIL"].duplicated(keep=False)
    regras["email_compartilhado_entre_clientes_sinalizado"] = int(df["EMAIL_DUPLICADO"].sum())

    expira_demais = df["PONTOS_A_EXPIRAR_90D"] > df["PONTOS_ACUMULADOS"]
    regras["pontos_a_expirar_limitados_ao_saldo"] = int(expira_demais.sum())
    df.loc[expira_demais, "PONTOS_A_EXPIRAR_90D"] = df.loc[expira_demais, "PONTOS_ACUMULADOS"]

    comentario = df["COMENTARIO_ULTIMO_CONTATO"].fillna("")
    mascarado = comentario.map(_mascarar_pii)
    regras["comentarios_com_dado_pessoal_mascarado"] = int((mascarado != comentario).sum())
    df["COMENTARIO_ULTIMO_CONTATO"] = mascarado.replace("", pd.NA)
    df["SENTIMENTO_SCORE"] = mascarado.map(_sentimento)
    df["SENTIMENTO_ULTIMO_CONTATO"] = df["SENTIMENTO_SCORE"].map(
        lambda s: None if pd.isna(s) else ("POSITIVO" if s > 0 else "NEGATIVO" if s < 0 else "NEUTRO"))

    for col in ["DATA_ULTIMO_VOO", "COMENTARIO_ULTIMO_CONTATO"]:
        df[col] = df[col].replace("", pd.NA)

    invalidos = (~df["CATEGORIA_TIER"].isin(ORDEM_CATEGORIA) | ~df["ESTADO"].isin(AEROPORTOS_UF)
                 | ~df["RISCO_CHURN"].isin(PROPENSAO_CHURN) | (df["VOOS_ANO"] < 0) | (df["PONTOS_ACUMULADOS"] < 0)
                 ).fillna(True).astype(bool)
    regras["registros_invalidos_descartados"] = int(invalidos.sum())
    df = df[~invalidos]

    regras["registros_silver"] = len(df)
    silver = df.sort_values("CUSTOMER_ID")[list(TIPOS_SILVER)].reset_index(drop=True)
    return silver, regras


def _mascarar_pii(texto: str) -> str:
    texto = RE_CPF.sub("[CPF]", texto)
    texto = RE_EMAIL.sub("[EMAIL]", texto)
    return RE_TELEFONE.sub("[TELEFONE]", texto)


def _sentimento(texto: str) -> float | None:
    """Sentimento léxico simples em PT-BR (-1 a 1). Linha de base, substituível por um LLM."""
    if not texto:
        return None
    tokens = re.findall(r"[a-z]+", _sem_acento(texto).lower())
    pos = neg = 0
    for i, t in enumerate(tokens):
        negado = i > 0 and tokens[i - 1] in NEGADORES
        if t in LEXICO_POSITIVO:
            neg, pos = (neg + 1, pos) if negado else (neg, pos + 1)
        elif t in LEXICO_NEGATIVO:
            pos, neg = (pos + 1, neg) if negado and t != "resolveu" else (pos, neg + 1)
    return 0.0 if pos + neg == 0 else round((pos - neg) / (pos + neg), 2)


# ================================================================ GOLD
def construir_gold(silver: pd.DataFrame) -> pd.DataFrame:
    """Calcula valor (RFM/CLV), risco com fatores explicáveis, persona, próxima viagem e ação."""
    df = silver.copy()
    ref = pd.Timestamp(DATA_REFERENCIA)
    voos = df["VOOS_ANO"].astype(float)

    df["MESES_RELACIONAMENTO"] = ((ref - pd.to_datetime(df["DATA_CADASTRO"])).dt.days // 30).astype("Int64")
    df["DIAS_DESDE_ULTIMO_VOO"] = (ref - pd.to_datetime(df["DATA_ULTIMO_VOO"])).dt.days.astype("Int64")
    df["TENDENCIA_VOOS"] = ((voos - df["VOOS_ANO_ANTERIOR"]) / df["VOOS_ANO_ANTERIOR"].clip(lower=1)).round(2).astype(float)
    pagos = (voos - df["RESGATES_PONTOS_12M"]).clip(lower=0)
    df["TICKET_MEDIO"] = (df["GASTO_TOTAL_12M"] / pagos.where(pagos > 0)).round(2).fillna(0.0)
    pct_resgate = (df["RESGATES_PONTOS_12M"] / voos.where(voos > 0)).fillna(0.0).astype(float)

    # --- risco de evasão: scorecard logístico com contribuição de cada fator
    intervalo = 365 / voos.clip(lower=1)
    recencia_rel = (df["DIAS_DESDE_ULTIMO_VOO"].astype(float).fillna(730) / intervalo).clip(upper=4)
    nps = df["NPS_ULTIMO"].astype(float)
    contrib = pd.DataFrame({
        "recencia": 0.9 * (recencia_rel - 1).clip(lower=0),
        "queda": 1.6 * (-df["TENDENCIA_VOOS"]).clip(lower=0),
        "atrasos": 0.35 * df["ATRASOS_SOFRIDOS_12M"].astype(float).clip(upper=4),
        "reclamacoes": 0.5 * df["RECLAMACOES_12M"].astype(float).clip(upper=3),
        "nps": (0.25 * (7 - nps).clip(lower=0)).fillna(0.0),
        "sentimento": 0.6 * df["SENTIMENTO_ULTIMO_CONTATO"].eq("NEGATIVO").astype(float),
        "cartao": -0.5 * df["CARTAO_AZUL_ITAU"].ne("NENHUM").astype(float),
        "clube": -0.4 * df["CLUBE_AZUL"].ne("NENHUM").astype(float),
    })
    df["PROB_CHURN_90D"] = (1 / (1 + np.exp(-(-2.2 + contrib.sum(axis=1))))).round(3)
    textos = {
        "recencia": lambda r: f"Sem voar há {r.DIAS_DESDE_ULTIMO_VOO if pd.notna(r.DIAS_DESDE_ULTIMO_VOO) else 'mais de 730'} dias",
        "queda": lambda r: f"Voos caíram de {r.VOOS_ANO_ANTERIOR} para {r.VOOS_ANO} no ano",
        "atrasos": lambda r: f"{r.ATRASOS_SOFRIDOS_12M} atraso(s)/cancelamento(s) em 12 meses",
        "reclamacoes": lambda r: f"{r.RECLAMACOES_12M} reclamação(ões) em 12 meses",
        "nps": lambda r: f"Último NPS {r.NPS_ULTIMO} (detrator)",
        "sentimento": lambda r: "Último contato com sentimento negativo",
    }
    fatores = []
    for (_, linha), (_, c) in zip(df.iterrows(), contrib.iterrows()):
        top = [k for k, v in c.sort_values(ascending=False).items() if v > 0.15 and k in textos][:3]
        fatores.append("; ".join(textos[k](linha) for k in top) or "Sem fatores de risco relevantes")
    df["FATORES_RISCO"] = fatores

    # --- valor: RFM + potencial e CLV de 36 meses descontado
    rank = lambda s: s.rank(pct=True)  # noqa: E731
    potencial = (df["CATEGORIA_TIER"].map(ORDEM_CATEGORIA.index) / 3 + df["CARTAO_AZUL_ITAU"].ne("NENHUM")
                 + df["CLUBE_AZUL"].ne("NENHUM") + rank(df["TICKET_MEDIO"]) + df["MOTIVO_VIAGEM"].eq("CORPORATIVO")) / 5
    recencia_score = 1 - rank(df["DIAS_DESDE_ULTIMO_VOO"].astype(float).fillna(9999))
    df["SCORE_VALOR"] = (100 * (0.35 * rank(df["GASTO_TOTAL_12M"]) + 0.25 * rank(voos)
                                + 0.15 * recencia_score + 0.25 * potencial)).round(1)
    retencao_anual = (1 - df["PROB_CHURN_90D"]) ** 4
    receita_anual = df["GASTO_TOTAL_12M"] * (1 + 0.5 * df["TENDENCIA_VOOS"].clip(-0.5, 0.5))
    df["CLV_ESTIMADO_36M"] = sum(receita_anual * retencao_anual ** t / 1.12 ** t for t in (1, 2, 3)).round(2)
    pct_clv = rank(df["CLV_ESTIMADO_36M"])
    df["ALTO_VALOR"] = pct_clv > 0.80
    df["SEGMENTO_VALOR"] = np.select([pct_clv > 0.80, pct_clv > 0.40], ["ALTO", "MEDIO"], "BAIXO")

    # --- persona (regra explicável sobre o comportamento observado)
    personas = []
    for r, resg in zip(df.itertuples(index=False), pct_resgate):
        if r.VOOS_ANO <= 2:
            personas.append(("Ocasional", f"{r.VOOS_ANO} voo(s) no ano"))
        elif r.MOTIVO_VIAGEM == "CORPORATIVO" or (r.MOTIVO_VIAGEM == "MISTO" and r.VOOS_ANO >= 10 and r.ANTECEDENCIA_MEDIA_DIAS <= 15):
            personas.append(("Executivo Frequente", f"{r.MOTIVO_VIAGEM.lower()}, {r.VOOS_ANO} voos/ano, compra com {r.ANTECEDENCIA_MEDIA_DIAS} dias"))
        elif resg >= 0.35 or (r.CLUBE_AZUL != "NENHUM" and r.TARIFA_PREFERIDA == "AZUL"):
            personas.append(("Caçador de Pontos", f"{resg:.0%} dos voos com pontos, clube {r.CLUBE_AZUL.lower()}"))
        else:
            personas.append(("Lazer & Família", f"{r.MOTIVO_VIAGEM.lower()}, {r.ACOMPANHANTES_MEDIA} acompanhante(s), internacional={r.VIAJA_INTERNACIONAL}"))
    df["PERSONA"], df["PERSONA_MOTIVO"] = zip(*personas)

    # --- previsão da próxima viagem (como e quando o cliente vai viajar)
    ultimo = pd.to_datetime(df["DATA_ULTIMO_VOO"])
    estimada = (ultimo + pd.to_timedelta(intervalo, unit="D")).clip(lower=ref + pd.Timedelta(days=3))
    tem_historico = voos > 0
    df["PROXIMA_VIAGEM_DATA"] = estimada.where(tem_historico).dt.date
    janela = (estimada - pd.to_timedelta(df["ANTECEDENCIA_MEDIA_DIAS"].astype(float), unit="D")).clip(lower=ref)
    df["PROXIMA_VIAGEM_JANELA_COMPRA"] = janela.where(tem_historico).dt.date
    df["PROXIMA_VIAGEM_ROTA"] = df["ROTA_FAVORITA"].where(tem_historico)
    df["PROXIMA_VIAGEM_TARIFA"] = df["TARIFA_PREFERIDA"].where(tem_historico)
    df["PROXIMA_VIAGEM_PAGAMENTO"] = np.where(pct_resgate >= 0.5, "PONTOS", "DINHEIRO")
    df.loc[~tem_historico, "PROXIMA_VIAGEM_PAGAMENTO"] = None
    df["PROXIMA_VIAGEM_CONFIANCA"] = np.select(
        [~tem_historico, (voos >= 8) & (recencia_rel <= 1.2), voos >= 3], ["SEM_HISTORICO", "ALTA", "MEDIA"], "BAIXA")

    # --- fidelidade: projeção de categoria pelas regras 2026
    projecao, proxima, faltam = [], [], []
    for r in df.itertuples(index=False):
        cat = _categoria_por_atividade(r.VOOS_ANO, r.GASTO_TOTAL_12M)
        for produto in (r.CARTAO_AZUL_ITAU, r.CLUBE_AZUL):
            cat = max(cat, CATEGORIA_POR_PRODUTO.get(produto, "Basico"), key=ORDEM_CATEGORIA.index)
        projecao.append(cat)
        i = ORDEM_CATEGORIA.index(cat)
        if i + 1 < len(ORDEM_CATEGORIA):
            alvo = ORDEM_CATEGORIA[i + 1]
            proxima.append(alvo)
            faltam.append(max(0, REGRAS_CATEGORIA[alvo][0] - int(r.VOOS_ANO)))
        else:
            proxima.append(None)
            faltam.append(None)
    df["CATEGORIA_PROJETADA"], df["PROXIMA_CATEGORIA"] = projecao, proxima
    df["FALTAM_TRECHOS_PROXIMA"] = pd.array(faltam, dtype="Int64")
    df["RISCO_REBAIXAMENTO"] = df["CATEGORIA_PROJETADA"].map(ORDEM_CATEGORIA.index) < df["CATEGORIA_TIER"].map(ORDEM_CATEGORIA.index)

    # --- próxima melhor ação (regras de negócio; o agente de IA redige a mensagem)
    acoes = [_proxima_acao(r) for r in df.itertuples(index=False)]
    df["ACAO_RECOMENDADA"], df["ACAO_DESCRICAO"] = zip(*acoes)
    df["CANAL_CONTATO"] = np.where(df["OPT_IN_MARKETING"], df["CANAL_CONTATO_PREFERIDO"], "SOMENTE_SERVICO")
    df["PRIORIDADE_CRM"] = (100 * rank(df["CLV_ESTIMADO_36M"] * df["PROB_CHURN_90D"])).round(1)
    df["DATA_REFERENCIA"] = DATA_REFERENCIA

    return df.sort_values("PRIORIDADE_CRM", ascending=False)[list(TIPOS_GOLD)].reset_index(drop=True)


def _categoria_por_atividade(trechos: int, gasto: float) -> str:
    atingida = "Basico"
    for cat, (min_trechos, min_pontos, regra, gasto_alt) in REGRAS_CATEGORIA.items():
        pontos = gasto  # R$ 1 em passagens = 1 ponto qualificável
        ok = (trechos >= min_trechos or pontos >= min_pontos) if regra == "OU" else (trechos >= min_trechos and pontos >= min_pontos)
        if ok or (gasto_alt and gasto >= gasto_alt):
            atingida = cat
    return atingida


def _proxima_acao(r) -> tuple[str, str]:
    destino = r.ROTA_FAVORITA.split("-")[1]
    if r.ALTO_VALOR and r.RECLAMACOES_12M > 0 and r.SENTIMENTO_ULTIMO_CONTATO == "NEGATIVO":
        return "RECUPERACAO_SERVICO", f"Contato proativo do relacionamento e bônus de pontos pela experiência ruim ({r.ATRASOS_SOFRIDOS_12M} atraso(s) em 12 meses)."
    if r.PONTOS_A_EXPIRAR_90D >= 3_000:
        return "RESGATE_PONTOS", f"{r.PONTOS_A_EXPIRAR_90D} pontos expiram em 90 dias: sugerir resgate na rota {r.ROTA_FAVORITA}."
    if r.RISCO_REBAIXAMENTO:
        faltam = max(0, REGRAS_CATEGORIA[r.CATEGORIA_TIER][0] - r.VOOS_ANO)
        return "PROTECAO_CATEGORIA", f"Faltam {faltam} trecho(s) para manter {r.CATEGORIA_TIER}: campanha de bônus de pontos qualificáveis na rota {r.ROTA_FAVORITA}."
    if r.PROXIMA_CATEGORIA and pd.notna(r.FALTAM_TRECHOS_PROXIMA) and 0 < r.FALTAM_TRECHOS_PROXIMA <= 3:
        return "UPGRADE_CATEGORIA", f"Faltam {r.FALTAM_TRECHOS_PROXIMA} trecho(s) para {r.PROXIMA_CATEGORIA}: mostrar benefícios e oferta na rota {r.ROTA_FAVORITA}."
    if r.PERSONA == "Executivo Frequente" and r.TARIFA_PREFERIDA == "AZUL":
        return "UPSELL_MAIS_AZUL", f"Oferecer MaisAzul ou Espaço Azul na rota {r.ROTA_FAVORITA}."
    if r.PERSONA == "Lazer & Família":
        quando = r.PROXIMA_VIAGEM_JANELA_COMPRA if pd.notna(r.PROXIMA_VIAGEM_JANELA_COMPRA) else "a próxima temporada"
        return "PACOTE_AZUL_VIAGENS", f"Pacote Azul Viagens para {destino}, contato a partir de {quando}."
    if r.PERSONA == "Caçador de Pontos" and r.CARTAO_AZUL_ITAU == "NENHUM":
        return "CARTAO_COBRANDED", "Oferecer cartão Azul Itaú ou upgrade de plano do Clube Azul para acelerar pontos."
    if r.PROB_CHURN_90D >= 0.5:
        return "WINBACK", f"Oferta personalizada com bônus de pontos na rota {r.ROTA_FAVORITA}."
    return "RELACIONAMENTO", f"Comunicação personalizada com novidades da rota {r.ROTA_FAVORITA}."


def resumo_gold(gold: pd.DataFrame, silver: pd.DataFrame) -> dict:
    domestico = ~gold["ROTA_FAVORITA"].str.split("-").str[1].isin(DESTINOS_INTERNACIONAIS)
    return {
        "data_referencia": DATA_REFERENCIA.isoformat(),
        "clientes": len(gold),
        "alto_valor": int(gold["ALTO_VALOR"].sum()),
        "receita_12m_total": round(float(gold["GASTO_TOTAL_12M"].sum()), 2),
        "pct_receita_alto_valor": round(float(gold.loc[gold["ALTO_VALOR"], "GASTO_TOTAL_12M"].sum() / gold["GASTO_TOTAL_12M"].sum()), 3),
        "por_persona": gold["PERSONA"].value_counts().to_dict(),
        "por_acao": gold["ACAO_RECOMENDADA"].value_counts().to_dict(),
        "prob_churn_media_por_risco_origem": gold.groupby("RISCO_CHURN")["PROB_CHURN_90D"].mean().round(3).to_dict(),
        "ticket_medio_domestico": round(float(gold.loc[domestico & (gold["TICKET_MEDIO"] > 0), "TICKET_MEDIO"].mean()), 2),
        "referencia_anac_tarifa_media": TARIFA_MEDIA_ANAC,
        "clientes_da_base": int(silver["ORIGEM_REGISTRO"].eq(CSV_BASE.name).sum()),
    }


# ================================================================ SNOWFLAKE
def gerar_ddl(database: str = "AZUL_DATA_LAKE") -> str:
    def create(schema: str, tabela: str, tipos: dict[str, str], comentario: str) -> str:
        cols = ",\n".join(f"    {c} {t}" for c, t in tipos.items())
        return f"CREATE OR REPLACE TABLE {database}.{schema}.{tabela} (\n{cols}\n) COMMENT = '{comentario}';\n"

    contexto_ia = ",\n       ".join(COLUNAS_CONTEXTO_IA)
    return "\n".join([
        "-- Gerado por `python pipeline_datalake.py ddl` (fonte: pipeline_datalake.py). Complementa 05_setup_snowflake_medalhao.sql.",
        f"CREATE DATABASE IF NOT EXISTS {database};",
        *(f"CREATE SCHEMA IF NOT EXISTS {database}.{s};" for s in ("BRONZE", "SILVER", "GOLD")),
        "",
        create("BRONZE", "CLIENTES_AZUL_RAW", {c: "VARCHAR" for c in COLUNAS_BRONZE}, "Base expandida como chegou (texto bruto)"),
        create("SILVER", "CLIENTES_AZUL", TIPOS_SILVER, "Clientes higienizados, tipados e deduplicados"),
        create("GOLD", "CLIENTES_AZUL", TIPOS_GOLD, "Valor, risco, persona, proxima viagem e acao por cliente"),
        "-- Visão sem dados pessoais para o agente de IA (LGPD).",
        f"CREATE OR REPLACE VIEW {database}.GOLD.VW_CONTEXTO_IA AS\nSELECT {contexto_ia}\nFROM {database}.GOLD.CLIENTES_AZUL;",
        "",
    ])


def enviar_snowflake() -> None:
    from snowflake.connector.pandas_tools import write_pandas
    from database import get_snowflake_connection

    database = os.getenv("SNOWFLAKE_DATABASE", "AZUL_DATA_LAKE")
    conn = get_snowflake_connection()
    try:
        conn.execute_string(gerar_ddl(database))
        for schema, tabela, arquivo in CAMADAS_SNOWFLAKE:
            df = pd.read_csv(arquivo, dtype=str, keep_default_na=False) if schema == "BRONZE" else pd.read_csv(arquivo)
            ok, _, linhas, _ = write_pandas(conn, df, tabela, database=database, schema=schema,
                                            overwrite=True, quote_identifiers=False, use_logical_type=True)
            print(f"{schema}.{tabela}: {linhas} linhas enviadas ({'ok' if ok else 'falhou'})")
    finally:
        conn.close()


def trazer_gold() -> None:
    from database import get_snowflake_connection

    database = os.getenv("SNOWFLAKE_DATABASE", "AZUL_DATA_LAKE")
    conn = get_snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {database}.GOLD.CLIENTES_AZUL ORDER BY PRIORIDADE_CRM DESC")
        gold = cur.fetch_pandas_all()
    finally:
        conn.close()
    gold.columns = [c.upper() for c in gold.columns]
    for col, tipo in TIPOS_GOLD.items():
        if tipo.endswith(",0)"):
            gold[col] = gold[col].astype("Int64")
    gold[list(TIPOS_GOLD)].to_csv(GOLD_CSV, index=False)
    print(f"GOLD.CLIENTES_AZUL -> {GOLD_CSV.relative_to(BASE_DIR)} ({len(gold)} clientes)")


# ================================================================ CLI
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapa", choices=["gerar", "tratar", "ddl", "enviar", "trazer"])
    parser.add_argument("--total", type=int, default=TOTAL_PADRAO, help="clientes na base expandida")
    args = parser.parse_args()

    if args.etapa == "gerar":
        bronze = gerar_bronze(pd.read_csv(CSV_BASE), total=args.total)
        BRONZE_CSV.parent.mkdir(parents=True, exist_ok=True)
        bronze.to_csv(BRONZE_CSV, index=False)
        print(f"Bronze: {len(bronze)} registros -> {BRONZE_CSV.relative_to(BASE_DIR)}")
    elif args.etapa == "tratar":
        bronze = pd.read_csv(BRONZE_CSV, dtype=str, keep_default_na=False)
        silver, relatorio = tratar_silver(bronze)
        silver.to_csv(SILVER_CSV, index=False)
        RELATORIO_SILVER.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        gold = construir_gold(silver)
        gold.to_csv(GOLD_CSV, index=False)
        RESUMO_GOLD.write_text(json.dumps(resumo_gold(gold, silver), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Silver: {len(silver)} clientes | Gold: {len(gold)} clientes")
        print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    elif args.etapa == "ddl":
        DDL_SQL.write_text(gerar_ddl(), encoding="utf-8")
        print(f"DDL -> {DDL_SQL.relative_to(BASE_DIR)}")
    elif args.etapa == "enviar":
        enviar_snowflake()
    elif args.etapa == "trazer":
        trazer_gold()


if __name__ == "__main__":
    main()
