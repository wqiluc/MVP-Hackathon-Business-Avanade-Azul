import duckdb
import pandas as pd

from data.gold.duckdb_transformer import DuckDBGoldTransformer


EXPECTED_COLUMNS = [
    "client_identifier",
    "tier",
    "frequency",
    "recency_days",
    "total_spend",
    "flight_incidents",
    "avg_ticket",
    "high_risk_flag",
]


def _connect_with_silver_table(tmp_path, dataframe):
    conn = duckdb.connect(str(tmp_path / "gold-test.duckdb"))
    for schema in ("bronze", "silver", "gold"):
        conn.execute(f"CREATE SCHEMA {schema}")
    conn.register("silver_input", dataframe)
    conn.execute("CREATE TABLE silver.cleaned_clients AS SELECT * FROM silver_input")
    conn.unregister("silver_input")
    return conn


def test_transform_creates_gold_with_exact_columns_and_preserved_values(tmp_path):
    silver = pd.DataFrame({
        "client_identifier": ["AZ-a1b2c3d4", "AZ-extra"],
        "tier": ["DIAMANTE", "OURO"],
        "frequency": [3, 4],
        "recency_days": [20, 30],
        "total_spend": [10.0, 20.0],
        "flight_incidents": [0, 0],
        "silver_extra": ["not propagated", "not propagated"],
    })
    conn = _connect_with_silver_table(tmp_path, silver)

    try:
        DuckDBGoldTransformer.transform_client_features(conn)
        result = conn.execute("SELECT * FROM gold.client_features").fetchdf()
    finally:
        conn.close()

    assert list(result.columns) == EXPECTED_COLUMNS
    assert result.loc[0, "client_identifier"] == "AZ-a1b2c3d4"
    assert result.loc[0, "tier"] == "DIAMANTE"
    assert result.loc[0, "frequency"] == 3
    assert result.loc[0, "recency_days"] == 20
    assert result.loc[0, "total_spend"] == 10.0
    assert result.loc[0, "flight_incidents"] == 0
    assert result.loc[0, "avg_ticket"] == 3.33
    assert result.loc[0, "high_risk_flag"] == 0
    assert result.loc[1, "avg_ticket"] == 5.0
    assert "silver_extra" not in result.columns


def test_transform_calculates_high_risk_flag_for_both_rules(tmp_path):
    silver = pd.DataFrame({
        "client_identifier": ["AZ-incidents", "AZ-recency", "AZ-low-risk"],
        "tier": ["OURO", "OURO", "OURO"],
        "frequency": [1, 1, 1],
        "recency_days": [10, 61, 60],
        "total_spend": [10.0, 10.0, 10.0],
        "flight_incidents": [2, 0, 1],
    })
    conn = _connect_with_silver_table(tmp_path, silver)

    try:
        DuckDBGoldTransformer.transform_client_features(conn)
        result = conn.execute(
            "SELECT client_identifier, high_risk_flag FROM gold.client_features "
            "ORDER BY client_identifier"
        ).fetchall()
    finally:
        conn.close()

    assert result == [
        ("AZ-incidents", 1),
        ("AZ-low-risk", 0),
        ("AZ-recency", 1),
    ]


def test_transform_returns_null_avg_ticket_and_uses_case_else_for_null_risk(tmp_path):
    silver = pd.DataFrame({
        "client_identifier": ["AZ-zero", "AZ-null-spend", "AZ-null-values"],
        "tier": ["OURO", "OURO", None],
        "frequency": [0, 2, None],
        "recency_days": [10, 10, None],
        "total_spend": [20.0, None, None],
        "flight_incidents": [0, 0, None],
    })
    conn = _connect_with_silver_table(tmp_path, silver)

    try:
        DuckDBGoldTransformer.transform_client_features(conn)
        result = conn.execute(
            "SELECT client_identifier, tier, frequency, recency_days, total_spend, "
            "flight_incidents, avg_ticket, high_risk_flag "
            "FROM gold.client_features ORDER BY client_identifier"
        ).fetchall()
    finally:
        conn.close()

    assert result == [
        ("AZ-null-spend", "OURO", 2, 10, None, 0, None, 0),
        ("AZ-null-values", None, None, None, None, None, None, 0),
        ("AZ-zero", "OURO", 0, 10, 20.0, 0, None, 0),
    ]


def test_transform_creates_empty_gold_when_silver_is_empty(tmp_path):
    silver = pd.DataFrame({
        "client_identifier": pd.Series(dtype="str"),
        "tier": pd.Series(dtype="str"),
        "frequency": pd.Series(dtype="int64"),
        "recency_days": pd.Series(dtype="int64"),
        "total_spend": pd.Series(dtype="float64"),
        "flight_incidents": pd.Series(dtype="int64"),
    })
    conn = _connect_with_silver_table(tmp_path, silver)

    try:
        DuckDBGoldTransformer.transform_client_features(conn)
        result = conn.execute("SELECT * FROM gold.client_features").fetchdf()
    finally:
        conn.close()

    assert result.empty
    assert list(result.columns) == EXPECTED_COLUMNS


def test_transform_replaces_existing_gold_and_keeps_supplied_connection_open(
    tmp_path, monkeypatch
):
    silver = pd.DataFrame({
        "client_identifier": ["AZ-current"],
        "tier": ["PRATA"],
        "frequency": [1],
        "recency_days": [5],
        "total_spend": [10.0],
        "flight_incidents": [0],
    })
    conn = _connect_with_silver_table(tmp_path, silver)
    conn.execute("CREATE TABLE gold.client_features AS SELECT 'old' AS previous")

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("The transformer must use the supplied connection")

    monkeypatch.setattr(duckdb, "connect", unexpected_connection)
    try:
        DuckDBGoldTransformer.transform_client_features(conn)
        result = conn.execute(
            "SELECT client_identifier FROM gold.client_features"
        ).fetchall()
    finally:
        conn.close()

    assert result == [("AZ-current",)]
