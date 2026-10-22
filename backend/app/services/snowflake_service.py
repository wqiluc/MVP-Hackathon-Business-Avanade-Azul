from pathlib import Path

import pandas as pd

from app.config import settings
from app.services.snapshot import execution_id, logger, validate_candidate


_SNOWFLAKE_SQL_DIR = (
    Path(__file__).resolve().parents[3] / "infrastructure" / "snowflake"
)
_BRONZE_TABLE = "BRONZE.BRONZE_CLIENTS"
_SILVER_TABLE = "SILVER.CLEANED_CLIENTS"
_GOLD_TABLE = "GOLD.CLIENT_FEATURES"


class SnowflakeDataLake:
    """Snowflake implementation of the CRM medallion data lake."""

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
    def _execute_sql_file(
        conn, filename: str, candidate_tables: dict[str, str] | None = None,
    ) -> None:
        sql_file = _SNOWFLAKE_SQL_DIR / filename
        if not sql_file.is_file():
            raise FileNotFoundError(f"SQL Snowflake não encontrado: {sql_file}")

        sql = sql_file.read_text(encoding="utf-8")
        if candidate_tables:
            for active, candidate in candidate_tables.items():
                sql = sql.replace(active, candidate)
            sql = sql.replace("CREATE OR REPLACE TABLE", "CREATE TEMPORARY TABLE")
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
        run_id = execution_id()
        tables = {
            _BRONZE_TABLE: f"BRONZE.CANDIDATE_{run_id.upper()}",
            _SILVER_TABLE: f"SILVER.CANDIDATE_{run_id.upper()}",
            _GOLD_TABLE: f"GOLD.CANDIDATE_{run_id.upper()}",
        }
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

            cls._execute(
                conn,
                f"CREATE TEMPORARY TABLE {tables[_BRONZE_TABLE]} "
                "LIKE BRONZE.BRONZE_CLIENTS",
            )
            cls._write_candidate(conn, bronze, tables[_BRONZE_TABLE], write_pandas)
            cls._execute_sql_file(conn, "02_transform_silver.sql", tables)
            cls._execute_sql_file(conn, "03_transform_gold.sql", tables)

            silver = cls._read_table(conn, tables[_SILVER_TABLE])
            gold = cls._read_table(conn, tables[_GOLD_TABLE])
            from app.services.datalake_service import DataLakeService

            gold["churn_score"], scoring_status = DataLakeService.score_gold(gold)
            cls._execute(conn, f"DELETE FROM {tables[_GOLD_TABLE]}")
            cls._write_candidate(
                conn, gold.rename(columns=str.upper), tables[_GOLD_TABLE], write_pandas,
            )
            persisted_bronze = cls._read_table(conn, tables[_BRONZE_TABLE])
            persisted_gold = cls._read_table(conn, tables[_GOLD_TABLE])
            if len(persisted_bronze) != len(df_raw) or set(persisted_bronze["id_cliente"]) != set(df_raw["id_cliente"]):
                raise RuntimeError("Bronze candidata incompleta.")
            validate_candidate(df_raw, silver, persisted_gold, scoring_status)
            cls._publish(conn, tables, run_id)

            return {
                "status": "success",
                "processed_rows": len(gold),
                "scoring_status": scoring_status,
                "layers": [
                    _BRONZE_TABLE,
                    "SILVER",
                    _GOLD_TABLE,
                ],
            }
        except Exception:
            logger.warning("snapshot candidate_failed execution_id=%s backend=snowflake", run_id)
            raise
        finally:
            conn.close()

    @staticmethod
    def _execute(conn, sql: str, parameters=None) -> None:
        cursor = conn.cursor()
        try:
            if parameters is None:
                cursor.execute(sql)
            else:
                cursor.execute(sql, parameters)
        finally:
            cursor.close()

    @staticmethod
    def _write_candidate(conn, frame, table: str, writer) -> None:
        schema, name = table.split(".")
        success, _, count, _ = writer(
            conn, frame, name, schema=schema, auto_create_table=False, overwrite=False,
        )
        if not success or count != len(frame):
            raise RuntimeError("Falha ao persistir todos os registros do snapshot candidato.")

    @classmethod
    def _publish(cls, conn, tables: dict[str, str], run_id: str) -> None:
        # CTAS bootstraps exactly one mutex row, even when two sessions provision it.
        cls._execute(conn, """
            CREATE TABLE IF NOT EXISTS GOLD.SNAPSHOT_PUBLICATION AS
            SELECT CAST(NULL AS VARCHAR) AS EXECUTION_ID,
                   CURRENT_TIMESTAMP() AS PUBLISHED_AT
        """)
        cls._execute(conn, "ALTER SESSION SET LOCK_TIMEOUT = 5")
        cls._execute(conn, "BEGIN TRANSACTION")
        try:
            # UPDATE holds the publication lock until COMMIT/ROLLBACK across workers.
            cls._execute(
                conn,
                "UPDATE GOLD.SNAPSHOT_PUBLICATION "
                "SET EXECUTION_ID = %s, PUBLISHED_AT = CURRENT_TIMESTAMP()",
                (run_id,),
            )
            metadata = cls._read_table(conn, "GOLD.SNAPSHOT_PUBLICATION")
            if len(metadata) != 1:
                raise RuntimeError("Controle de publicação inválido.")
            for active, candidate in tables.items():
                columns = ", ".join(cls._read_table(conn, candidate).columns.str.upper())
                cls._execute(conn, f"DELETE FROM {active}")
                cls._execute(
                    conn, f"INSERT INTO {active} ({columns}) SELECT {columns} FROM {candidate}",
                )
            cls._execute(conn, "COMMIT")
        except Exception:
            cls._execute(conn, "ROLLBACK")
            logger.warning("snapshot rolled_back execution_id=%s backend=snowflake", run_id)
            raise
        logger.info("snapshot published execution_id=%s backend=snowflake", run_id)

    @staticmethod
    def _read_table(connection, table: str) -> pd.DataFrame:
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table}")
            frame = cursor.fetch_pandas_all()
            frame.columns = [str(column).lower() for column in frame.columns]
            return frame
        finally:
            cursor.close()

    @classmethod
    def read_gold(cls, conn=None) -> pd.DataFrame:
        owns_connection = conn is None
        connection = conn or cls.get_connection()
        try:
            return cls._read_table(connection, _GOLD_TABLE)
        finally:
            if owns_connection:
                connection.close()
