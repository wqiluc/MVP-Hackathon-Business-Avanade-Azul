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
    assert "TO_VARCHAR(ID_CLIENTE) AS CLIENT_IDENTIFIER" in silver
    assert "MD5(" not in silver
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


def test_ingestion_scoring_waits_for_a_registered_model(monkeypatch):
    import pandas as pd

    from app.services.datalake_service import DataLakeService

    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    gold = pd.DataFrame({"frequency": [2], "high_risk_flag": [1]})
    monkeypatch.setattr("ml.models.mlflow_tracker.configure_tracking", lambda uri: None)
    monkeypatch.setattr(
        "ml.models.mlflow_tracker.get_active_churn_model",
        lambda: None,
    )

    scores, status = DataLakeService.score_gold(gold)

    assert len(scores) == 1 and pd.isna(scores[0])
    assert status == "awaiting_model_registration"


def test_ingestion_scoring_uses_the_registered_model_via_serving(monkeypatch):
    import pandas as pd

    from app.services.datalake_service import DataLakeService

    serving_url = "http://mlflow.test/invocations"
    gold = pd.DataFrame({"frequency": [2]})
    calls = []
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", serving_url)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr("ml.models.mlflow_tracker.configure_tracking", lambda uri: None)
    monkeypatch.setattr(
        "ml.models.mlflow_tracker.get_active_churn_model",
        lambda: object(),
    )

    def fake_predict(df):
        calls.append(df)
        return [0.25]

    monkeypatch.setattr("app.services.inference_service.predict_churn", fake_predict)

    scores, status = DataLakeService.score_gold(gold)

    assert scores == [0.25]
    assert status == "scored"
    assert calls == [gold]


def test_ingestion_without_tracking_keeps_scores_missing_without_external_calls(monkeypatch):
    import pandas as pd
    from unittest.mock import Mock
    from app.services.datalake_service import DataLakeService

    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    registry = Mock(side_effect=AssertionError("Registry must not be contacted"))
    monkeypatch.setattr("ml.models.mlflow_tracker.get_active_churn_model", registry)
    scores, status = DataLakeService.score_gold(pd.DataFrame({"frequency": [2]}))

    assert pd.isna(scores[0])
    assert status == "awaiting_model_registration"
    registry.assert_not_called()


def test_database_bootstrap_sql_creates_the_documented_default_database():
    sql = _sql("00_create_database.sql")
    assert "CREATE DATABASE IF NOT EXISTS AZUL_DATA_LAKE" in sql
    assert "USE DATABASE AZUL_DATA_LAKE" in sql


def test_real_snowflake_pipeline_matches_duckdb_and_mlflow_serving(
    tmp_path, monkeypatch
):
    import os
    from ml.models.mlflow_tracker import MODEL_NAME

    required = (
        settings.SNOWFLAKE_ACCOUNT,
        settings.SNOWFLAKE_USER,
        settings.SNOWFLAKE_PASSWORD,
        settings.SNOWFLAKE_WAREHOUSE,
        settings.MLFLOW_SERVING_URL,
        settings.MLFLOW_TRACKING_URI,
        MODEL_NAME,
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
    if test_database != "CRM_TEST_E2E":
        pytest.fail(
            "SNOWFLAKE_TEST_DATABASE deve ser CRM_TEST_E2E; "
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
            "tier": ["  diamante ", "SAFIRA", "básico"],
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
        "scoring_status": "scored",
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
            cursor.execute("SELECT * FROM BRONZE.BRONZE_CLIENTS")
            persisted_bronze = cursor.fetch_pandas_all()
            persisted_bronze.columns = [
                str(column).lower() for column in persisted_bronze.columns
            ]
            assert set(raw["id_cliente"]).isdisjoint(
                set(persisted_bronze["id_cliente"])
            )
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
        DuckDBBronzeWriter.write_raw_clients(duckdb_conn, persisted_bronze)
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
