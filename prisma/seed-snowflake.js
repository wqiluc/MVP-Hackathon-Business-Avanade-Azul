require('dotenv').config();
const { fakerPT_BR: faker } = require('@faker-js/faker');
const { executeQuery } = require('../src/config/snowflake');
const fs = require('fs');
const path = require('path');

const TOTAL_CLIENTES = 2000;
const DIVISOES = ['VOOS_COMERCIAIS', 'AZUL_VIAGENS', 'AZUL_CARGO', 'AZUL_CONECTA'];
const NIVEIS = ['Básico', 'Topázio', 'Safira', 'Diamante'];
const STATUS = ['NOVO_LEAD', 'ATIVO', 'EM_RISCO', 'CHURN_PROVAVEL'];
const CANAIS = ['Parceiro Bancário (Inter Loop)', 'App Azul', 'Busca Orgânica', 'Agência Parceira'];

async function gerarDadosSinteticos() {
  console.log(`Iniciando geração sintética de ${TOTAL_CLIENTES} clientes...`);

  const clientesBronze = [];
  const clientesSilver = [];
  const analisesGold = [];

  for (let i = 0; i < TOTAL_CLIENTES; i++) {
    const status = faker.helpers.arrayElement(STATUS);
    const emRisco = status === 'EM_RISCO' || status === 'CHURN_PROVAVEL';
    const isLead = status === 'NOVO_LEAD';

    const riscoScore = emRisco
      ? Number(faker.number.float({ min: 0.65, max: 0.98, fractionDigits: 2 }))
      : Number(faker.number.float({ min: 0.05, max: 0.40, fractionDigits: 2 }));

    const divisaoAtual = faker.helpers.arrayElement(DIVISOES);
    const divisaoSugerida = faker.helpers.arrayElement(DIVISOES.filter(d => d !== divisaoAtual));
    const gasto = isLead ? 0 : Number(faker.number.float({ min: 350, max: 9000, fractionDigits: 2 }));
    const pontosExpirar = emRisco ? faker.number.int({ min: 2000, max: 25000 }) : 0;
    const cpf = faker.string.numeric(11);

    const clienteObj = {
      cpf,
      nome: faker.person.fullName(),
      email: faker.internet.email().toLowerCase(),
      uf: faker.location.state({ abbreviated: true }),
      nivelFidelidade: isLead ? 'Básico' : faker.helpers.arrayElement(NIVEIS),
      saldoPontos: isLead ? 0 : faker.number.int({ min: 3000, max: 150000 }),
      pontosAExpirar: pontosExpirar,
      canalAquisicao: faker.helpers.arrayElement(CANAIS),
      statusRetencao: status,
      riscoChurnScore: riscoScore,
      divisaoPrincipal: divisaoAtual,
      divisaoCrossSell: divisaoSugerida,
      ltvTotalGasto: gasto
    };

    clientesBronze.push({
      origem: 'SEED_SINTETICO_2000',
      formato: 'JSON_BATCH',
      payload: JSON.stringify(clienteObj)
    });

    clientesSilver.push([
      clienteObj.cpf,
      clienteObj.nome,
      clienteObj.email,
      clienteObj.uf,
      clienteObj.nivelFidelidade,
      clienteObj.saldoPontos,
      clienteObj.pontosAExpirar,
      clienteObj.canalAquisicao
    ]);

    analisesGold.push([
      clienteObj.cpf,
      clienteObj.statusRetencao,
      clienteObj.riscoChurnScore,
      clienteObj.ltvTotalGasto,
      clienteObj.divisaoPrincipal,
      clienteObj.divisaoCrossSell,
      emRisco
        ? `Retenção Urgente: Ofertar voucher na divisão ${divisaoSugerida} antes que ${pontosExpirar} pontos expirem`
        : `Aquisição Cross-Sell: Apresentar benefícios da divisão ${divisaoSugerida}`
    ]);
  }

  const pastaBronze = path.join(__dirname, '../datalake/bronze');
  if (!fs.existsSync(pastaBronze)) fs.mkdirSync(pastaBronze, { recursive: true });
  fs.writeFileSync(
    path.join(pastaBronze, 'seed_2000_clientes.json'),
    JSON.stringify(clientesBronze, null, 2),
    'utf-8'
  );

  return { clientesBronze, clientesSilver, analisesGold };
}

async function popularSnowflakeEmLote() {
  const { clientesBronze, clientesSilver, analisesGold } = await gerarDadosSinteticos();
  const BATCH_SIZE = 500;

  console.log('Populando Camada BRONZE no Snowflake...');
  for (let i = 0; i < clientesBronze.length; i += BATCH_SIZE) {
    const lote = clientesBronze.slice(i, i + BATCH_SIZE);
    const sqlValues = lote
      .map(item => `('SEED_2000', 'JSON', '${item.payload.replace(/'/g, "''")}')`)
      .join(',');

    // Executa PARSE_JSON via SELECT em vez de VALUES direto
    await executeQuery(`
      INSERT INTO AZUL_DATA_LAKE.BRONZE.INGESTAO_RAW (origem_arquivo, formato_original, payload_bruto)
      SELECT column1, column2, PARSE_JSON(column3)
      FROM VALUES ${sqlValues}
    `);
    console.log(`Bronze: ${Math.min(i + BATCH_SIZE, clientesBronze.length)}/${clientesBronze.length} inseridos.`);
  }

  console.log('Populando Camada SILVER no Snowflake...');
  for (let i = 0; i < clientesSilver.length; i += BATCH_SIZE) {
    const lote = clientesSilver.slice(i, i + BATCH_SIZE);
    const sqlValues = lote
      .map(c => `('${c[0]}', '${c[1].replace(/'/g, "''")}', '${c[2].replace(/'/g, "''")}', '${c[3]}', '${c[4]}', ${c[5]}, ${c[6]}, '${c[7].replace(/'/g, "''")}')`)
      .join(',');

    await executeQuery(`
      INSERT INTO AZUL_DATA_LAKE.SILVER.CLIENTES (cpf, nome, email, uf, nivel_fidelidade, saldo_pontos, pontos_a_expirar, canal_aquisicao)
      VALUES ${sqlValues}
    `);
    console.log(`Silver: ${Math.min(i + BATCH_SIZE, clientesSilver.length)}/${clientesSilver.length} inseridos.`);
  }

  console.log('Populando Camada GOLD no Snowflake...');
  for (let i = 0; i < analisesGold.length; i += BATCH_SIZE) {
    const lote = analisesGold.slice(i, i + BATCH_SIZE);
    const sqlValues = lote
      .map(g => `('${g[0]}', '${g[1]}', ${g[2]}, ${g[3]}, '${g[4]}', '${g[5]}', '${g[6].replace(/'/g, "''")}')`)
      .join(',');

    await executeQuery(`
      INSERT INTO AZUL_DATA_LAKE.GOLD.ANALISE_RETENCAO (cpf, status_retencao, risco_churn_score, ltv_total_gasto, divisao_principal, divisao_cross_sell, acao_recomendada)
      VALUES ${sqlValues}
    `);
    console.log(`Gold: ${Math.min(i + BATCH_SIZE, analisesGold.length)}/${analisesGold.length} inseridos.`);
  }

  console.log('\nData Lake populado com sucesso: 2.000 clientes sincronizados nas camadas Bronze, Silver e Gold!');
}

popularSnowflakeEmLote()
  .then(() => process.exit(0))
  .catch(err => {
    console.error('Erro na carga dos dados:', err);
    process.exit(1);
  });