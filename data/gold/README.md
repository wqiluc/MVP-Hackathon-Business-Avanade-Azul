# Gold layer

`duckdb_transformer.py` materializa features analíticas, incluindo `avg_ticket`
e `high_risk_flag`; a persistência do `churn_score` ocorre depois, via
`DuckDBAdapter`.
