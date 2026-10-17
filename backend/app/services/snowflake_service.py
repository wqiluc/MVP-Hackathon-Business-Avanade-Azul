import pandas as pd
from app.config import settings


class SnowflakeDataLake:
    """Data Lake Medalhão oficial (Bronze/Silver/Gold) no Snowflake."""

    @staticmethod
    def get_connection():
        import snowflake.connector
        return snowflake.connector.connect(
            user=settings.SNOWFLAKE_USER, password=settings.SNOWFLAKE_PASSWORD,
            account=settings.SNOWFLAKE_ACCOUNT, warehouse=settings.SNOWFLAKE_WAREHOUSE,
            database=settings.SNOWFLAKE_DATABASE, role=settings.SNOWFLAKE_ROLE or None,
        )

    @classmethod
    def process_ingestion(cls, df_raw: pd.DataFrame) -> dict:
        from snowflake.connector.pandas_tools import write_pandas
        from app.services.inference_service import predict_churn

        conn = cls.get_connection()
        try:
            df_raw = df_raw.copy()
            df_raw.columns = [c.upper() for c in df_raw.columns]
            write_pandas(conn, df_raw, "BRONZE_CLIENTS", schema="BRONZE",
                         auto_create_table=True, overwrite=True)
            cur = conn.cursor()
            cur.execute("CALL PROCESS_SILVER_LAYER()")  # limpeza + hash LGPD
            cur.execute("CALL PROCESS_GOLD_LAYER()")    # feature store
            gold = cls.read_gold(conn)
            gold["churn_score"] = predict_churn(gold)
            write_pandas(conn, gold.rename(columns=str.upper), "CLIENT_FEATURES",
                         schema="GOLD", overwrite=True)
            return {"status": "success", "processed_rows": len(gold),
                    "layers": ["BRONZE.BRONZE_CLIENTS", "SILVER", "GOLD.CLIENT_FEATURES"]}
        finally:
            conn.close()

    @classmethod
    def read_gold(cls, conn=None) -> pd.DataFrame:
        own = conn is None
        conn = conn or cls.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM GOLD.CLIENT_FEATURES")
            df = cur.fetch_pandas_all()
            df.columns = [c.lower() for c in df.columns]
            return df
        finally:
            if own:
                conn.close()
