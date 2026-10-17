const { PrismaClient } = require('@prisma/client');
const { fakerPT_BR: faker } = require('@faker-js/faker');
const fs = require('fs');
const path = require('path');

const prisma = new PrismaClient();

const DIVISOES = ['VOOS_COMERCIAIS', 'AZUL_VIAGENS', 'AZUL_CARGO', 'AZUL_CONECTA'];
const NIVEIS = ['Básico', 'Topázio', 'Safira', 'Diamante'];
const STATUS = ['NOVO_LEAD', 'ATIVO', 'EM_RISCO', 'CHURN_PROVAVEL'];
const ROTAS = ['REC-VCP', 'GRU-REC', 'CNF-SSA', 'REC-FEN', 'SDU-CGH', 'VCP-MCO'];
const CANAIS = ['Parceiro Bancário (Inter Loop)', 'App Azul', 'Busca Orgânica', 'Agência Parceira'];

async function main() {
  console.log('Limpando Data Lake...');
  await prisma.goldAnaliseRetencao.deleteMany();
  await prisma.silverInteracao.deleteMany();
  await prisma.silverCliente.deleteMany();
  await prisma.bronzeIngestao.deleteMany();

  console.log('Iniciando Pipeline Sintético: Gerando Camadas BRONZE -> SILVER -> GOLD...');
  const loteBruto = [];

  for (let i = 0; i < 50; i++) {
    const status = faker.helpers.arrayElement(STATUS);
    const emRisco = status === 'EM_RISCO' || status === 'CHURN_PROVAVEL';
    const isLead = status === 'NOVO_LEAD';

    const riscoScore = emRisco
      ? faker.number.float({ min: 0.65, max: 0.98, fractionDigits: 2 })
      : faker.number.float({ min: 0.05, max: 0.40, fractionDigits: 2 });

    const divisaoAtual = faker.helpers.arrayElement(DIVISOES);
    const divisaoSugerida = faker.helpers.arrayElement(DIVISOES.filter(d => d !== divisaoAtual));
    const gasto = isLead ? 0 : faker.number.float({ min: 350, max: 9000, fractionDigits: 2 });
    const pontosExpirar = emRisco ? faker.number.int({ min: 2000, max: 25000 }) : 0;

    const dadoCliente = {
      cpf: faker.string.numeric(11),
      nome: faker.person.fullName(),
      email: faker.internet.email().toLowerCase(),
      uf: faker.location.state({ abbreviated: true }),
      nivelFidelidade: isLead ? 'Básico' : faker.helpers.arrayElement(NIVEIS),
      saldoPontos: isLead ? 0 : faker.number.int({ min: 3000, max: 150000 }),
      pontosAExpirar: pontosExpirar,
      canalAquisicao: faker.helpers.arrayElement(CANAIS)
    };

    loteBruto.push({ ...dadoCliente, status, divisaoAtual, gasto });

    // 1. Grava na SILVER (Dados Limpos) e na GOLD (Inteligência de Negócio)
    await prisma.silverCliente.create({
      data: {
        ...dadoCliente,
        interacoes: {
          create: [{
            divisao: divisaoAtual,
            tipoAcao: isLead ? 'COTACAO_ABANDONADA' : (emRisco ? 'RECLAMACAO' : 'COMPRA'),
            valorGasto: gasto,
            rota: faker.helpers.arrayElement(ROTAS),
            avaliacaoNPS: emRisco ? faker.number.int({ min: 1, max: 5 }) : faker.number.int({ min: 8, max: 10 })
          }]
        },
        metricasGold: {
          create: {
            statusRetencao: status,
            riscoChurnScore: riscoScore,
            ltvTotalGasto: gasto,
            divisaoPrincipal: divisaoAtual,
            divisaoCrossSell: divisaoSugerida,
            acaoRecomendada: emRisco
              ? `Retenção Urgente: Ofertar voucher na divisão ${divisaoSugerida} antes que ${pontosExpirar} pontos expirem`
              : `Aquisição Cross-Sell: Apresentar benefícios da divisão ${divisaoSugerida}`
          }
        }
      }
    });
  }

  // Salva o arquivo bruto na pasta física datalake/bronze e registra na tabela Bronze
  const caminhoBronze = path.join(__dirname, '../datalake/bronze/seed_inicial_raw.json');
  fs.writeFileSync(caminhoBronze, JSON.stringify(loteBruto, null, 2), 'utf-8');

  await prisma.bronzeIngestao.create({
    data: {
      origemArquivo: 'seed_inicial_raw.json',
      formatoOriginal: 'JSON_SYNTHETIC',
      caminhoDataLake: 'datalake/bronze/seed_inicial_raw.json',
      payloadBruto: JSON.stringify(loteBruto.slice(0, 3)) + ' ... [50 registros]'
    }
  });

  console.log('Data Lake populado com sucesso (Camadas Bronze, Silver e Gold sincronizadas)!');
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
