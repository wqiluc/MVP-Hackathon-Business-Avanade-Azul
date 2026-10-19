from pathlib import Path

import pandas as pd

from app.config import settings


_SNOWFLAKE_SQL_DIR = (
    Path(__file__).resolve().parents[3] / "infrastructure" / "snowflake"
)


class SnowflakeDataLake:
    """Snowflake implementation of the AeroShield medallion data lake."""

    @staticmethod
    def get_connection(
        *,
        login_timeout: int | None = None,
        network_timeout: int | None = None,
        statement_timeout: int | None = None,
    ):
        missing = [
            name
            for name in (
                "SNOWFLAKE_ACCOUNT",
                "SNOWFLAKE_USER",
                "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_DATABASE",
                "SNOWFLAKE_WAREHOUSE",
            )
            if not getattr(settings, name)
        ]
        if missing:
            raise RuntimeError(
                "Snowflake backend selecionado, mas faltam configurações: "
                + ", ".join(missing)
            )

        import snowflake.connector

        connection_options = {}
        if login_timeout is not None:
            connection_options["login_timeout"] = login_timeout
        if network_timeout is not None:
            connection_options["network_timeout"] = network_timeout
        if statement_timeout is not None:
            connection_options["session_parameters"] = {
                "STATEMENT_TIMEOUT_IN_SECONDS": statement_timeout
            }

        return snowflake.connector.connect(
            account=settings.SNOWFLAKE_ACCOUNT,
            user=settings.SNOWFLAKE_USER,
            password=settings.SNOWFLAKE_PASSWORD,
            database=settings.SNOWFLAKE_DATABASE,
            warehouse=settings.SNOWFLAKE_WAREHOUSE,
            role=settings.SNOWFLAKE_ROLE or None,
            **connection_options,
        )

    @staticmethod
    def _execute_sql_file(conn, filename: str) -> None:
        sql_file = _SNOWFLAKE_SQL_DIR / filename
        if not sql_file.is_file():
            raise FileNotFoundError(f"SQL Snowflake não encontrado: {sql_file}")

        sql = sql_file.read_text(encoding="utf-8")
        statements = []
        for statement in sql.split(";"):
            statement = "\n".join(
                line
                for line in statement.splitlines()
                if not line.lstrip().startswith("--")
            ).strip()
            if statement:
                statements.append(statement)

        cursor = conn.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
        finally:
            cursor.close()

    @classmethod
    def ensure_schemas(cls, conn) -> None:
        cls._execute_sql_file(conn, "01_schemas.sql")

    @classmethod
    def process_ingestion(cls, df_raw: pd.DataFrame) -> dict:
        if df_raw.empty:
            raise ValueError("O arquivo enviado está vazio.")

        conn = cls.get_connection()
        try:
            from snowflake.connector.pandas_tools import write_pandas

            cls.ensure_schemas(conn)
            bronze = df_raw.copy()
            bronze.columns = [str(column).upper() for column in bronze.columns]
            if bronze.columns.duplicated().any():
                raise ValueError(
                    "Os nomes das colunas ficam duplicados após normalização "
                    "para maiúsculas no Snowflake."
                )

            success, _, written_rows, _ = write_pandas(
                conn,
                bronze,
                "BRONZE_CLIENTS",
                schema="BRONZE",
                auto_create_table=True,
                overwrite=True,
            )
            if not success or written_rows != len(bronze):
                raise RuntimeError(
                    "Falha ao gravar todos os registros em "
                    "BRONZE.BRONZE_CLIENTS: "
                    f"success={success}, gravados={written_rows}, "
                    f"esperados={len(bronze)}."
                )

            cls._execute_sql_file(conn, "02_transform_silver.sql")
            cls._execute_sql_file(conn, "03_transform_gold.sql")

            gold = cls.read_gold(conn)
            from app.services.datalake_service import DataLakeService

            gold["churn_score"], scoring_status = DataLakeService.score_gold(gold)
            success, _, written_rows, _ = write_pandas(
                conn,
                gold.rename(columns=str.upper),
                "CLIENT_FEATURES",
                schema="GOLD",
                overwrite=True,
            )
            if not success or written_rows != len(gold):
                raise RuntimeError(
                    "Falha ao gravar todos os scores em GOLD.CLIENT_FEATURES: "
                    f"success={success}, gravados={written_rows}, "
                    f"esperados={len(gold)}."
                )

            return {
                "status": "success",
                "processed_rows": len(gold),
                "scoring_status": scoring_status,
                "layers": [
                    "BRONZE.BRONZE_CLIENTS",
                    "SILVER",
                    "GOLD.CLIENT_FEATURES",
                ],
            }
        finally:
            conn.close()

    @classmethod
    def read_gold(cls, conn=None) -> pd.DataFrame:
        owns_connection = conn is None
        connection = conn or cls.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT * FROM GOLD.CLIENT_FEATURES")
            gold = cursor.fetch_pandas_all()
            gold.columns = [str(column).lower() for column in gold.columns]
            return gold
        finally:
            cursor.close()
            if owns_connection:
                connection.close()
