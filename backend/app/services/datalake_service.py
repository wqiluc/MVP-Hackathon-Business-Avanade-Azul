import os
import duckdb
import pandas as pd
from app.config import settings

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
        conn = cls.get_connection()
        try:
            # 1. BRONZE (Raw)
            if file_type == "xlsx":
                df_raw = pd.read_excel(file_path)
            elif file_type == "json":
                df_raw = pd.read_json(file_path)
            else:
                raise ValueError("Formato não suportado. Envie arquivos Excel (.xlsx) ou JSON.")

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

            row_count = conn.execute("SELECT COUNT(*) FROM gold.client_features").fetchone()[0]

            return {
                "status": "success",
                "processed_rows": row_count,
                "layers": ["bronze.raw_clients", "silver.cleaned_clients", "gold.client_features"]
            }
        finally:
            conn.close()
