class DuckDBSilverTransformer:
    @staticmethod
    def transform_cleaned_clients(conn):
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
