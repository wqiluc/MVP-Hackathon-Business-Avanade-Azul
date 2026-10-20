import numpy as np
import pandas as pd
import pytest

import pipeline_datalake as pl


@pytest.fixture(scope="module")
def camadas():
    original = pd.read_csv(pl.CSV_BASE)
    bronze = pl.gerar_bronze(original)
    silver, relatorio = pl.tratar_silver(bronze)
    gold = pl.construir_gold(silver)
    return original, bronze, silver, relatorio, gold


def test_silver_preserva_todos_os_clientes_da_base(camadas):
    original, _, silver, _, _ = camadas
    assert len(silver) == len(original) and silver["CUSTOMER_ID"].is_unique
    colunas = pl.COLUNAS_ORIGINAIS
    preservados = silver.set_index("CUSTOMER_ID").loc[original["CUSTOMER_ID"]].reset_index()[colunas]
    pd.testing.assert_frame_equal(preservados.astype(str), original[colunas].astype(str))


def test_expansao_por_bootstrap_mantem_a_base():
    base = pd.read_csv(pl.CSV_BASE).head(500)
    expandida = pl.expandir_base(base, 800, np.random.default_rng(pl.SEED))
    assert len(expandida) == 800 and expandida["CUSTOMER_ID"].is_unique
    pd.testing.assert_frame_equal(expandida.head(500)[pl.COLUNAS_ORIGINAIS], base)
    assert set(expandida["CATEGORIA_TIER"]) <= set(pl.ORDEM_CATEGORIA)


def test_geracao_reprodutivel():
    base = pd.read_csv(pl.CSV_BASE).head(2000)
    pd.testing.assert_frame_equal(pl.gerar_bronze(base, total=2000), pl.gerar_bronze(base, total=2000))


def test_silver_corrige_os_problemas_da_bronze(camadas):
    _, bronze, silver, relatorio, _ = camadas
    assert len(bronze) > len(silver)
    assert relatorio["duplicatas_removidas_mantendo_mais_recente"] == len(bronze) - len(silver)
    assert set(silver["CATEGORIA_TIER"]) <= set(pl.ORDEM_CATEGORIA)
    assert set(silver["ESTADO"]) <= set(pl.AEROPORTOS_UF)
    assert silver["NPS_ULTIMO"].dropna().between(0, 10).all()
    assert silver["TARIFA_PREFERIDA"].isin(pl.MULT_TARIFA).all()
    assert (silver["EMAIL"] == silver["EMAIL"].str.lower()).all()
    assert (silver["PONTOS_A_EXPIRAR_90D"] <= silver["PONTOS_ACUMULADOS"]).all()


def test_silver_mascara_dados_pessoais_no_texto_livre(camadas):
    _, bronze, silver, relatorio, _ = camadas
    assert bronze["COMENTARIO_ULTIMO_CONTATO"].str.contains(pl.RE_CPF).any()
    comentarios = silver["COMENTARIO_ULTIMO_CONTATO"].dropna()
    for padrao in (pl.RE_CPF, pl.RE_EMAIL, pl.RE_TELEFONE):
        assert not comentarios.str.contains(padrao).any()
    assert relatorio["comentarios_com_dado_pessoal_mascarado"] > 0


def test_sentimento_lexico():
    assert pl._sentimento("Voo pontual e tripulação muito atenciosa. Recomendo!") > 0
    assert pl._sentimento("Mais um atraso, descaso total.") < 0
    assert pl._sentimento("Voo normal, sem novidades.") == 0
    assert pl._sentimento("") is None


def test_gold_respeita_contrato_e_regras(camadas):
    *_, gold = camadas
    assert list(gold.columns) == list(pl.TIPOS_GOLD)
    assert gold["PROB_CHURN_90D"].between(0, 1).all()
    assert gold["SCORE_VALOR"].between(0, 100).all()
    assert set(gold["PERSONA"]) == {"Executivo Frequente", "Lazer & Família", "Caçador de Pontos", "Ocasional"}
    assert 0.15 < gold["ALTO_VALOR"].mean() < 0.25
    assert gold["PRIORIDADE_CRM"].is_monotonic_decreasing


def test_risco_calculado_concorda_com_o_risco_de_origem(camadas):
    *_, gold = camadas
    media = gold.groupby("RISCO_CHURN")["PROB_CHURN_90D"].mean()
    assert media["Alto"] > media["Medio"] > media["Baixo"]


def test_sem_consentimento_somente_contato_de_servico(camadas):
    _, _, silver, _, gold = camadas
    sem_optin = set(silver.loc[~silver["OPT_IN_MARKETING"], "CUSTOMER_ID"])
    assert (gold.loc[gold["CUSTOMER_ID"].isin(sem_optin), "CANAL_CONTATO"] == "SOMENTE_SERVICO").all()


def test_contexto_ia_nao_leva_dados_pessoais():
    assert not {"NOME", "EMAIL", "COMENTARIO_ULTIMO_CONTATO"} & set(pl.COLUNAS_CONTEXTO_IA)


def test_ddl_versionado_esta_sincronizado_com_o_codigo():
    assert pl.DDL_SQL.read_text(encoding="utf-8") == pl.gerar_ddl()
