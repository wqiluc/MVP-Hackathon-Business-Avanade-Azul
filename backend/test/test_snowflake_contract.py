import pytest

from app.config import settings
from app.services.snowflake_service import SnowflakeDataLake, _SNOWFLAKE_SQL_DIR


def _sql(filename: str) -> str:
    return (_SNOWFLAKE_SQL_DIR / filename).read_text(encoding="utf-8").upper()


def test_snowflake_sql_defines_the_canonical_medallion_contract():
    setup = _sql("01_schemas.sql")
    silver = _sql("02_transform_silver.sql")
    gold = _sql("03_transform_gold.sql")

    assert "CREATE SCHEMA IF NOT EXISTS BRONZE" in setup
    assert "CREATE SCHEMA IF NOT EXISTS SILVER" in setup
    assert "CREATE SCHEMA IF NOT EXISTS GOLD" in setup
    assert "BRONZE.BRONZE_CLIENTS" in setup
    for column in (
        "ID_CLIENTE",
        "TIER",
        "FREQUENCIA",
        "RECENCIA_DIAS",
        "GASTO_TOTAL",
        "INCIDENTES",
    ):
        assert column in setup

    assert "SILVER.CLEANED_CLIENTS" in silver
    for column in (
        "CLIENT_IDENTIFIER",
        "TIER",
        "FREQUENCY",
        "RECENCY_DAYS",
        "TOTAL_SPEND",
        "FLIGHT_INCIDENTS",
        "INGESTED_AT",
    ):
        assert column in silver
    assert "LOWER(SUBSTR(MD5(TO_VARCHAR(ID_CLIENTE)), 1, 8))" in silver
    assert "UPPER(TRIM(TIER))" in silver
    assert "WHERE ID_CLIENTE IS NOT NULL" in silver

    assert "GOLD.CLIENT_FEATURES" in gold
    for column in (
        "CLIENT_IDENTIFIER",
        "TIER",
        "FREQUENCY",
        "RECENCY_DAYS",
        "TOTAL_SPEND",
        "FLIGHT_INCIDENTS",
        "AVG_TICKET",
        "HIGH_RISK_FLAG",
        "CHURN_SCORE",
    ):
        assert column in gold
    assert "ROUND(TOTAL_SPEND / NULLIF(FREQUENCY, 0), 2)" in gold
    assert "FLIGHT_INCIDENTS >= 2 OR RECENCY_DAYS > 60" in gold
    assert "CAST(NULL AS FLOAT) AS CHURN_SCORE" in gold


def test_snowflake_sql_assets_are_resolved_from_the_source_tree_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _SNOWFLAKE_SQL_DIR.is_absolute()
    assert (_SNOWFLAKE_SQL_DIR / "01_schemas.sql").is_file()
    assert (_SNOWFLAKE_SQL_DIR / "02_transform_silver.sql").is_file()
    assert (_SNOWFLAKE_SQL_DIR / "03_transform_gold.sql").is_file()


def test_snowflake_connection_reports_missing_credentials_without_connecting(
    monkeypatch,
):
    for name in (
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_WAREHOUSE",
    ):
        monkeypatch.setattr(settings, name, "")

    with pytest.raises(RuntimeError, match="faltam configurações"):
        SnowflakeDataLake.get_connection()


def test_snowflake_scoring_rejects_missing_serving_without_local_fallback(
    monkeypatch,
):
    import pandas as pd

    from ml.inference.churn_predictor import ChurnPredictor

    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    gold = pd.DataFrame({"frequency": [2]})
    monkeypatch.setattr(
        ChurnPredictor,
        "predict",
        classmethod(
            lambda cls, df, serving_url, allow_local_inference=False: pytest.fail(
                "O predictor não deve ser chamado sem MLflow Serving."
            )
        ),
    )

    with pytest.raises(RuntimeError, match="MLFLOW_SERVING_URL"):
        SnowflakeDataLake._predict_churn(gold)


def test_snowflake_scoring_delegates_to_predictor_when_serving_is_configured(
    monkeypatch,
):
    import pandas as pd

    from ml.inference.churn_predictor import ChurnPredictor

    serving_url = "http://mlflow.test/invocations"
    gold = pd.DataFrame({"frequency": [2]})
    calls = []

    def fake_predict(
        cls, df, configured_url, allow_local_inference=False
    ):
        calls.append((df, configured_url, allow_local_inference))
        return [0.25]

    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", serving_url)
    monkeypatch.setattr(ChurnPredictor, "predict", classmethod(fake_predict))

    assert SnowflakeDataLake._predict_churn(gold) == [0.25]
    assert calls == [(gold, serving_url, False)]


def test_database_bootstrap_sql_creates_the_documented_default_database():
    sql = _sql("00_create_database.sql")
    assert "CREATE DATABASE IF NOT EXISTS AZUL_DATA_LAKE" in sql
    assert "USE DATABASE AZUL_DATA_LAKE" in sql


def test_real_snowflake_pipeline_matches_duckdb_and_mlflow_serving(
    tmp_path, monkeypatch
):
    import os
    import re

    required = (
        settings.SNOWFLAKE_ACCOUNT,
        settings.SNOWFLAKE_USER,
        settings.SNOWFLAKE_PASSWORD,
        settings.SNOWFLAKE_WAREHOUSE,
        settings.MLFLOW_SERVING_URL,
    )
    test_database = settings.SNOWFLAKE_TEST_DATABASE
    if (
        os.getenv("SNOWFLAKE_INTEGRATION_TESTS") != "1"
        or not all(required)
        or not test_database
    ):
        pytest.skip(
            "Habilite explicitamente Snowflake real, banco de teste dedicado e "
            "MLflow Serving para executar esta integração."
        )
    if not re.fullmatch(r"AEROSHIELD_TEST_[A-Z0-9_]+", test_database):
        pytest.fail(
            "SNOWFLAKE_TEST_DATABASE deve começar com AEROSHIELD_TEST_; "
            "a integração não aceita banco de produção."
        )

    import duckdb
    import pandas as pd
    import snowflake.connector

    bootstrap = snowflake.connector.connect(
        account=settings.SNOWFLAKE_ACCOUNT,
        user=settings.SNOWFLAKE_USER,
        password=settings.SNOWFLAKE_PASSWORD,
        warehouse=settings.SNOWFLAKE_WAREHOUSE,
        role=settings.SNOWFLAKE_ROLE or None,
    )
    try:
        cursor = bootstrap.cursor()
        try:
            cursor.execute(f'CREATE DATABASE IF NOT EXISTS "{test_database}"')
        finally:
            cursor.close()
    finally:
        bootstrap.close()

    monkeypatch.setattr(settings, "SNOWFLAKE_DATABASE", test_database)
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "snowflake")

    raw = pd.DataFrame(
        {
            "id_cliente": ["integration-incident", "integration-recency", "zero-frequency"],
            "tier": ["  diamante ", "OURO", "prata"],
            "frequencia": [2, 4, 0],
            "recencia_dias": [20, 61, 10],
            "gasto_total": [200.0, 400.0, 25.0],
            "incidentes": [2, 0, 0],
        }
    )
    csv_file = tmp_path / "snowflake-integration.csv"
    raw.to_csv(csv_file, index=False)

    from app.services.datalake_service import DataLakeService
    from data.bronze.duckdb_writer import DuckDBBronzeWriter
    from data.gold.duckdb_transformer import DuckDBGoldTransformer
    from data.silver.duckdb_transformer import DuckDBSilverTransformer

    result = DataLakeService.process_ingestion(str(csv_file), "csv")
    assert result == {
        "status": "success",
        "processed_rows": len(raw),
        "layers": [
            "BRONZE.BRONZE_CLIENTS",
            "SILVER",
            "GOLD.CLIENT_FEATURES",
        ],
    }

    snowflake = SnowflakeDataLake.get_connection()
    try:
        cursor = snowflake.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM BRONZE.BRONZE_CLIENTS")
            assert cursor.fetchone()[0] == len(raw)
            cursor.execute("SELECT COUNT(*) FROM SILVER.CLEANED_CLIENTS")
            assert cursor.fetchone()[0] == len(raw)
        finally:
            cursor.close()
        actual = SnowflakeDataLake.read_gold(snowflake)
    finally:
        snowflake.close()

    duckdb_conn = duckdb.connect(":memory:")
    try:
        for schema in ("bronze", "silver", "gold"):
            duckdb_conn.execute(f"CREATE SCHEMA {schema}")
        DuckDBBronzeWriter.write_raw_clients(duckdb_conn, raw)
        DuckDBSilverTransformer.transform_cleaned_clients(duckdb_conn)
        DuckDBGoldTransformer.transform_client_features(duckdb_conn)
        expected = duckdb_conn.execute(
            "SELECT * FROM gold.client_features ORDER BY client_identifier"
        ).fetchdf()
    finally:
        duckdb_conn.close()

    gold_columns = list(expected.columns)
    actual = actual.sort_values("client_identifier").reset_index(drop=True)
    expected = expected.reset_index(drop=True)
    pd.testing.assert_frame_equal(
        actual[gold_columns],
        expected,
        check_dtype=False,
        check_exact=False,
        rtol=1e-6,
        atol=1e-6,
    )
    assert actual["churn_score"].notna().all()
    assert actual["churn_score"].between(0, 1).all()
