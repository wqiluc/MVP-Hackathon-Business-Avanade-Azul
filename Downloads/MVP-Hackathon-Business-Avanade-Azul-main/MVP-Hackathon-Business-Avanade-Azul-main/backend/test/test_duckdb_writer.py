import duckdb
import pandas as pd

from data.bronze.duckdb_writer import DuckDBBronzeWriter


def _connect_with_bronze_schema(tmp_path):
    conn = duckdb.connect(str(tmp_path / "azul_datalake.duckdb"))
    conn.execute("CREATE SCHEMA bronze")
    return conn


def test_write_raw_clients_preserves_columns_values_and_inferred_types(tmp_path):
    conn = _connect_with_bronze_schema(tmp_path)
    df_raw = pd.DataFrame({
        "id_cliente": [1, 2],
        "tier": ["DIAMANTE", "OURO"],
        "gasto_total": [1250.5, 800.0],
        "coluna_extra": [True, False],
    })

    try:
        DuckDBBronzeWriter.write_raw_clients(conn, df_raw)

        result = conn.execute("SELECT * FROM bronze.raw_clients").fetchdf()
        types = conn.execute(
            "SELECT typeof(id_cliente), typeof(tier), typeof(gasto_total), typeof(coluna_extra) "
            "FROM bronze.raw_clients LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    pd.testing.assert_frame_equal(result, df_raw)
    assert types == ("BIGINT", "VARCHAR", "DOUBLE", "BOOLEAN")


def test_write_raw_clients_replaces_previous_table(tmp_path):
    conn = _connect_with_bronze_schema(tmp_path)
    first_dataframe = pd.DataFrame({"old_column": [1, 2]})
    replacement = pd.DataFrame({"new_column": ["latest"]})

    try:
        DuckDBBronzeWriter.write_raw_clients(conn, first_dataframe)
        DuckDBBronzeWriter.write_raw_clients(conn, replacement)

        result = conn.execute("SELECT * FROM bronze.raw_clients").fetchdf()
    finally:
        conn.close()

    pd.testing.assert_frame_equal(result, replacement)


def test_write_raw_clients_uses_and_keeps_the_supplied_connection_open(tmp_path, monkeypatch):
    conn = _connect_with_bronze_schema(tmp_path)
    df_raw = pd.DataFrame({"value": [42]})

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("The writer must use the supplied connection")

    monkeypatch.setattr(duckdb, "connect", unexpected_connection)
    try:
        DuckDBBronzeWriter.write_raw_clients(conn, df_raw)

        result = conn.execute("SELECT value FROM bronze.raw_clients").fetchone()
        assert result == (42,)
    finally:
        conn.close()
