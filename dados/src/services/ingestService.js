const { executeQuery } = require('../config/snowflake');

async function ingerirNoSnowflake({ origemArquivo, formatoOriginal, payloadJson }) {
  // 1. Inserção na Camada Bronze (Payload VARIANT)
  const queryBronze = `
    INSERT INTO AZUL_DATA_LAKE.BRONZE.INGESTAO_RAW (origem_arquivo, formato_original, payload_bruto)
    SELECT ?, ?, PARSE_JSON(?)
  `;
  await executeQuery(queryBronze, [origemArquivo, formatoOriginal, JSON.stringify(payloadJson)]);

  // 2. Promoção Idempotente para Camada Silver (MERGE)
  const querySilver = `
    MERGE INTO AZUL_DATA_LAKE.SILVER.CLIENTES target
    USING (
      SELECT 
        $1:cpf::STRING AS cpf,
        $1:nome::STRING AS nome,
        $1:email::STRING AS email,
        $1:uf::STRING AS uf,
        $1:nivelFidelidade::STRING AS nivel_fidelidade,
        $1:saldoPontos::NUMBER AS saldo_pontos,
        $1:pontosAExpirar::NUMBER AS pontos_a_expirar,
        $1:canalAquisicao::STRING AS canal_aquisicao
      FROM VALUES (PARSE_JSON(?))
    ) source
    ON target.cpf = source.cpf
    WHEN MATCHED THEN
      UPDATE SET 
        target.saldo_pontos = source.saldo_pontos,
        target.pontos_a_expirar = source.pontos_a_expirar,
        target.atualizado_em = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
      INSERT (cpf, nome, email, uf, nivel_fidelidade, saldo_pontos, pontos_a_expirar, canal_aquisicao)
      VALUES (source.cpf, source.nome, source.email, source.uf, source.nivel_fidelidade, source.saldo_pontos, source.pontos_a_expirar, source.canal_aquisicao);
  `;
  await executeQuery(querySilver, [JSON.stringify(payloadJson)]);

  // 3. Atualização Analítica na Camada Gold
  const queryGold = `
    MERGE INTO AZUL_DATA_LAKE.GOLD.ANALISE_RETENCAO target
    USING (
      SELECT 
        cpf,
        CASE WHEN pontos_a_expirar > 5000 THEN 'EM_RISCO' ELSE 'ATIVO' END AS status_retencao,
        CASE WHEN pontos_a_expirar > 5000 THEN 0.85 ELSE 0.15 END AS risco_churn_score,
        'VOOS_COMERCIAIS' AS divisao_principal,
        'AZUL_VIAGENS' AS divisao_cross_sell,
        'Ofertar conversão de pontos expirando em vouchers Azul Viagens' AS acao_recomendada
      FROM AZUL_DATA_LAKE.SILVER.CLIENTES
      WHERE cpf = ?
    ) source
    ON target.cpf = source.cpf
    WHEN MATCHED THEN
      UPDATE SET target.risco_churn_score = source.risco_churn_score, target.calculado_em = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
      INSERT (cpf, status_retencao, risco_churn_score, ltv_total_gasto, divisao_principal, divisao_cross_sell, acao_recomendada)
      VALUES (source.cpf, source.status_retencao, source.risco_churn_score, 0, source.divisao_principal, source.divisao_cross_sell, source.acao_recomendada);
  `;
  await executeQuery(queryGold, [payloadJson.cpf]);
}

module.exports = { ingerirNoSnowflake };