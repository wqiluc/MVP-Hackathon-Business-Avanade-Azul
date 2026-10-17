import os
import duckdb
import pandas as pd
from app.config import settings
from data.ingestion.file_reader import FileReader

class DataLakeService:
    @staticmethod
    def get_connection():
        os.makedirs(os.path.dirname(settings.DUCKDB_PATH), exist_ok=True)
        return duckdb.connect(settings.DUCKDB_PATH)

    @classmethod
    def init_schema(cls):
        """Cria as camadas Medalhão (Bronze, Silver, Gold)."""
        conn = cls.get_connection()
        try:
            conn.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
            conn.execute("CREATE SCHEMA IF NOT EXISTS silver;")
            conn.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        finally:
            conn.close()

    @classmethod
    def process_ingestion(cls, file_path: str, file_type: str) -> dict:
        if settings.DATA_LAKE_BACKEND == "snowflake":
            from app.services.snowflake_service import SnowflakeDataLake
            return SnowflakeDataLake.process_ingestion(cls._ler_arquivo(file_path, file_type))

        conn = cls.get_connection()
        try:
            # 1. BRONZE (Raw)
            df_raw = cls._ler_arquivo(file_path, file_type)

            if df_raw.empty:
                raise ValueError("O arquivo enviado está vazio.")

            conn.execute("CREATE OR REPLACE TABLE bronze.raw_clients AS SELECT * FROM df_raw")

            # 2. SILVER (Cleaned & LGPD)
            conn.execute("""
                CREATE OR REPLACE TABLE silver.cleaned_clients AS
                SELECT 
                    'AZ-' || SUBSTR(MD5(CAST(id_cliente AS VARCHAR)), 1, 8) AS client_identifier,
                    UPPER(TRIM(tier)) AS tier,
                    CAST(frequencia AS INTEGER) AS frequency,
                    CAST(recencia_dias AS INTEGER) AS recency_days,
                    CAST(gasto_total AS DOUBLE) AS total_spend,
                    CAST(incidentes AS INTEGER) AS flight_incidents,
                    CURRENT_TIMESTAMP AS ingested_at
                FROM bronze.raw_clients
                WHERE id_cliente IS NOT NULL
            """)

            # 3. GOLD (Analytics & ML Features)
            conn.execute("""
                CREATE OR REPLACE TABLE gold.client_features AS
                SELECT 
                    client_identifier,
                    tier,
                    frequency,
                    recency_days,
                    total_spend,
                    flight_incidents,
                    ROUND(total_spend / NULLIF(frequency, 0), 2) AS avg_ticket,
                    CASE WHEN flight_incidents >= 2 OR recency_days > 60 THEN 1 ELSE 0 END AS high_risk_flag
                FROM silver.cleaned_clients
            """)

            cls._score_gold(conn)
            row_count = conn.execute("SELECT COUNT(*) FROM gold.client_features").fetchone()[0]

            return {
                "status": "success",
                "processed_rows": row_count,
                "layers": ["bronze.raw_clients", "silver.cleaned_clients", "gold.client_features"]
            }
        finally:
            conn.close()

    @staticmethod
    def _ler_arquivo(file_path: str, file_type: str) -> pd.DataFrame:
        return FileReader.read_file(file_path, file_type)

    @classmethod
    def _score_gold(cls, conn) -> None:
        """Inferência (MLflow Serving ou regras locais) gravada de volta na Gold."""
        from app.services.inference_service import predict_churn

        df = conn.execute("SELECT * FROM gold.client_features").fetchdf()
        df["churn_score"] = predict_churn(df)
        conn.execute("CREATE OR REPLACE TABLE gold.client_features AS SELECT * FROM df")

    @classmethod
    def read_gold(cls) -> pd.DataFrame:
        """Lê a camada Ouro (vazia se ainda não houve ingestão)."""
        if settings.DATA_LAKE_BACKEND == "snowflake":
            from app.services.snowflake_service import SnowflakeDataLake
            return SnowflakeDataLake.read_gold()
        conn = cls.get_connection()
        try:
            return conn.execute("SELECT * FROM gold.client_features").fetchdf()
        except duckdb.CatalogException:
            return pd.DataFrame()
        finally:
            conn.close()
