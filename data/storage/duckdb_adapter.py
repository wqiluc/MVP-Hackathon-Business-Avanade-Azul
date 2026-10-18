import os
from os import PathLike

import duckdb
import pandas as pd


class DuckDBAdapter:
    @staticmethod
    def connect(database_path: str | PathLike[str]) -> duckdb.DuckDBPyConnection:
        database_path = os.fspath(database_path)
        os.makedirs(os.path.dirname(database_path) or ".", exist_ok=True)
        return duckdb.connect(database_path)

    @staticmethod
    def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")

    @staticmethod
    def read_gold(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
        try:
            return conn.execute("SELECT * FROM gold.client_features").fetchdf()
        except duckdb.CatalogException:
            return pd.DataFrame()
