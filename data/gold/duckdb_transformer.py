class DuckDBGoldTransformer:
    @staticmethod
    def transform_client_features(conn):
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
