const { executeQuery } = require('../config/snowflake');
const XLSX = require('xlsx');
const fs = require('fs');
const path = require('path');

async function exportarRelatoriosGold() {
  const query = `
    SELECT 
      c.cpf AS "CPF",
      c.nome AS "Nome",
      c.email AS "Email",
      c.uf AS "UF",
      c.nivel_fidelidade AS "Fidelidade",
      c.saldo_pontos AS "Saldo_Pontos",
      c.pontos_a_expirar AS "Pontos_Expirando",
      g.status_retencao AS "Status_Retencao",
      g.risco_churn_score AS "Risco_Churn",
      g.divisao_principal AS "Divisao_Principal",
      g.divisao_cross_sell AS "Cross_Sell_Sugerido",
      g.acao_recomendada AS "Acao_Recomendada"
    FROM AZUL_DATA_LAKE.GOLD.ANALISE_RETENCAO g
    JOIN AZUL_DATA_LAKE.SILVER.CLIENTES c ON g.cpf = c.cpf
    ORDER BY g.risco_churn_score DESC
  `;

  const dadosGold = await executeQuery(query);

  const pastaGold = path.join(__dirname, '../../datalake/gold');
  if (!fs.existsSync(pastaGold)) fs.mkdirSync(pastaGold, { recursive: true });

  // 1. JSON
  fs.writeFileSync(path.join(pastaGold, 'gold_retencao_azul.json'), JSON.stringify(dadosGold, null, 2));

  // 2. XLSX e CSV
  const ws = XLSX.utils.json_to_sheet(dadosGold);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Gold_Azul');
  XLSX.writeFile(wb, path.join(pastaGold, 'gold_retencao_azul.xlsx'));
  XLSX.writeFile(wb, path.join(pastaGold, 'gold_retencao_azul.csv'), { bookType: 'csv' });

  // 3. TXT
  const txt = dadosGold.map(c => `[GOLD SNOWFLAKE] ${c.Nome} (${c.CPF}) | Churn: ${c.Risco_Churn} | Ação: ${c.Acao_Recomendada}`).join('\n');
  fs.writeFileSync(path.join(pastaGold, 'gold_retencao_azul.txt'), txt, 'utf-8');

  console.log('Exportação multiformato finalizada com sucesso direto do Snowflake!');
}

module.exports = { exportarRelatoriosGold };