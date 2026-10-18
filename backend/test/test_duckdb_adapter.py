import ast
from pathlib import Path

import duckdb
import pandas as pd

from data.storage.duckdb_adapter import DuckDBAdapter


def test_connect_creates_database_and_missing_parent_directory(tmp_path):
    database_path = tmp_path / "nested" / "storage" / "warehouse.duckdb"

    conn = DuckDBAdapter.connect(database_path)
    try:
        assert database_path.is_file()
        assert conn.execute("SELECT 1").fetchone() == (1,)
    finally:
        conn.close()


def test_init_schema_creates_schemas_and_is_idempotent(tmp_path):
    conn = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    try:
        DuckDBAdapter.init_schema(conn)
        DuckDBAdapter.init_schema(conn)

        schemas = {
            row[0]
            for row in conn.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"bronze", "silver", "gold"} <= schemas


def test_read_gold_returns_table_data(tmp_path):
    conn = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    conn.execute("CREATE SCHEMA gold")
    expected = pd.DataFrame({"client_identifier": ["AZ-test"], "score": [0.25]})
    conn.register("gold_input", expected)
    conn.execute("CREATE TABLE gold.client_features AS SELECT * FROM gold_input")
    conn.unregister("gold_input")

    try:
        result = DuckDBAdapter.read_gold(conn)
    finally:
        conn.close()

    pd.testing.assert_frame_equal(result, expected)


def test_read_gold_returns_empty_dataframe_when_table_is_missing(tmp_path):
    conn = duckdb.connect(str(tmp_path / "warehouse.duckdb"))
    conn.execute("CREATE SCHEMA gold")

    try:
        result = DuckDBAdapter.read_gold(conn)
    finally:
        conn.close()

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_adapter_uses_and_keeps_supplied_connection_open(tmp_path, monkeypatch):
    conn = DuckDBAdapter.connect(tmp_path / "warehouse.duckdb")
    DuckDBAdapter.init_schema(conn)
    conn.execute("CREATE TABLE gold.client_features AS SELECT 1 AS value")

    def unexpected_connect(*args, **kwargs):
        raise AssertionError("Adapter methods must use the supplied connection")

    monkeypatch.setattr(duckdb, "connect", unexpected_connect)
    try:
        result = DuckDBAdapter.read_gold(conn)
        assert result.loc[0, "value"] == 1
        assert conn.execute("SELECT 1").fetchone() == (1,)
    finally:
        conn.close()


def test_adapter_does_not_import_application_or_fastapi_modules():
    adapter_path = Path(__file__).parents[2] / "data" / "storage" / "duckdb_adapter.py"
    tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
    imported_modules = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(
        module == "app"
        or module.startswith("app.")
        or module == "fastapi"
        or module.startswith("fastapi.")
        for module in imported_modules
    )
