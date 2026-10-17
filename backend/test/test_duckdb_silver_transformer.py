import hashlib

import duckdb
import pandas as pd

from data.silver.duckdb_transformer import DuckDBSilverTransformer


def _connect_with_bronze_table(tmp_path, dataframe):
    conn = duckdb.connect(str(tmp_path / "silver-test.duckdb"))
    conn.execute("CREATE SCHEMA bronze")
    conn.execute("CREATE SCHEMA silver")
    conn.register("bronze_input", dataframe)
    conn.execute("CREATE TABLE bronze.raw_clients AS SELECT * FROM bronze_input")
    conn.unregister("bronze_input")
    return conn


def test_transform_creates_expected_silver_columns_and_transforms_values(tmp_path):
    bronze = pd.DataFrame({
        "id_cliente": ["123"],
        "tier": ["  dIaMonDe  "],
        "frequencia": ["7"],
        "recencia_dias": ["30"],
        "gasto_total": ["1250.5"],
        "incidentes": ["2"],
        "coluna_extra": ["not projected"],
    })
    conn = _connect_with_bronze_table(tmp_path, bronze)

    try:
        DuckDBSilverTransformer.transform_cleaned_clients(conn)
        result = conn.execute("SELECT * FROM silver.cleaned_clients").fetchdf()
    finally:
        conn.close()

    assert list(result.columns) == [
        "client_identifier",
        "tier",
        "frequency",
        "recency_days",
        "total_spend",
        "flight_incidents",
        "ingested_at",
    ]
    assert result.loc[0, "client_identifier"] == (
        "AZ-" + hashlib.md5(b"123").hexdigest()[:8]
    )
    assert result.loc[0, "tier"] == "DIAMONDE"
    assert result.loc[0, "frequency"] == 7
    assert result.loc[0, "recency_days"] == 30
    assert result.loc[0, "total_spend"] == 1250.5
    assert result.loc[0, "flight_incidents"] == 2
    assert pd.notna(result.loc[0, "ingested_at"])
    assert "coluna_extra" not in result.columns


def test_transform_excludes_null_ids_and_preserves_other_null_values(tmp_path):
    bronze = pd.DataFrame({
        "id_cliente": ["456", None],
        "tier": [None, "OURO"],
        "frequencia": [None, "9"],
        "recencia_dias": [None, "12"],
        "gasto_total": [None, "300.0"],
        "incidentes": [None, "1"],
        "coluna_extra": ["kept in Bronze", "excluded"],
    })
    conn = _connect_with_bronze_table(tmp_path, bronze)

    try:
        DuckDBSilverTransformer.transform_cleaned_clients(conn)
        result = conn.execute("SELECT * FROM silver.cleaned_clients").fetchdf()
    finally:
        conn.close()

    assert len(result) == 1
    assert result.loc[0, "client_identifier"] == (
        "AZ-" + hashlib.md5(b"456").hexdigest()[:8]
    )
    for column in ("tier", "frequency", "recency_days", "total_spend", "flight_incidents"):
        assert pd.isna(result.loc[0, column])
    assert pd.notna(result.loc[0, "ingested_at"])


def test_transform_replaces_previous_silver_table(tmp_path):
    bronze = pd.DataFrame({
        "id_cliente": ["789"],
        "tier": ["PRATA"],
        "frequencia": ["3"],
        "recencia_dias": ["10"],
        "gasto_total": ["100.0"],
        "incidentes": ["0"],
    })
    conn = _connect_with_bronze_table(tmp_path, bronze)
    conn.execute("CREATE TABLE silver.cleaned_clients AS SELECT 'old' AS previous")

    try:
        DuckDBSilverTransformer.transform_cleaned_clients(conn)
        columns = [row[0] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'silver' AND table_name = 'cleaned_clients' "
            "ORDER BY ordinal_position"
        ).fetchall()]
    finally:
        conn.close()

    assert columns == [
        "client_identifier",
        "tier",
        "frequency",
        "recency_days",
        "total_spend",
        "flight_incidents",
        "ingested_at",
    ]


def test_transform_uses_supplied_connection_without_closing_it(tmp_path, monkeypatch):
    bronze = pd.DataFrame({
        "id_cliente": ["101"],
        "tier": ["OURO"],
        "frequencia": ["1"],
        "recencia_dias": ["1"],
        "gasto_total": ["1.0"],
        "incidentes": ["0"],
    })
    conn = _connect_with_bronze_table(tmp_path, bronze)

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("The transformer must use the supplied connection")

    monkeypatch.setattr(duckdb, "connect", unexpected_connection)
    try:
        DuckDBSilverTransformer.transform_cleaned_clients(conn)
        row_count = conn.execute("SELECT COUNT(*) FROM silver.cleaned_clients").fetchone()[0]
    finally:
        conn.close()

    assert row_count == 1
