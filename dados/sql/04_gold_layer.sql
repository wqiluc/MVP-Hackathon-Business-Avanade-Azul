CREATE OR REPLACE VIEW AZUL_DATA_LAKE.GOLD.VW_METRICAS_RETENCAO AS
SELECT 
    categoria,
    COUNT(cliente_id) AS total_clientes,
    COUNT_IF(email_valido = TRUE) AS total_emails_validos
FROM AZUL_DATA_LAKE.SILVER.CLIENTES
GROUP BY categoria;