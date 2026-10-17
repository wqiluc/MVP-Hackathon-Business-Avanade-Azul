CREATE TABLE IF NOT EXISTS AZUL_DATA_LAKE.SILVER.CLIENTES (
    cliente_id VARCHAR(50) PRIMARY KEY,
    nome VARCHAR(150),
    categoria VARCHAR(30),
    email_valido BOOLEAN,
    atualizado_em TIMESTAMP_NTZ
);

-- Exemplo de query que popula a Silver a partir da Bronze
INSERT INTO AZUL_DATA_LAKE.SILVER.CLIENTES
SELECT 
    raw_payload:cliente_id::STRING AS cliente_id,
    TRIM(raw_payload:nome::STRING) AS nome,
    UPPER(COALESCE(raw_payload:categoria::STRING, 'BASICO')) AS categoria,
    raw_payload:email::STRING LIKE '%@%.%' AS email_valido,
    data_ingestao AS atualizado_em
FROM AZUL_DATA_LAKE.BRONZE.RAW_PASSAGEIROS
QUALIFY ROW_NUMBER() OVER (PARTITION BY raw_payload:cliente_id ORDER BY data_ingestao DESC) = 1;