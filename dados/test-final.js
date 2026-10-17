const fs = require('fs');
const path = require('path');
const { ingerirNoDataLake } = require('./src/services/ingestService');
const { exportarCamadaGold } = require('./src/services/exportService');
const prisma = require('./src/config/prisma');

async function testarDataLake() {
  console.log('1. Ingerindo texto bruto na Camada BRONZE e processando para SILVER e GOLD...');
  const resIngestao = await ingerirNoDataLake({
    body: "Cliente Fernanda (fernanda.recife@teste.com, CPF 555.444.333-22) reclamou de atraso na Azul Cargo e quer cancelar."
  });
  console.log('Ingest�o conclu�da:', resIngestao);

  console.log('\n2. Exportando Camada GOLD em todos os formatos (PDF, XLSX, CSV, JSON, TXT)...');
  const resGold = await exportarCamadaGold();
  console.log('Exporta��o Data Lake conclu�da:', resGold);
}

testarDataLake()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
