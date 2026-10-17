const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('1. Limpando arquivos antigos corrompidos por encoding...');
const arquivosParaLimpar = ['.env', 'prisma/schema.prisma', 'prisma/dev.db', 'prisma/dev.db-journal'];
arquivosParaLimpar.forEach(arq => {
  const p = path.join(__dirname, arq);
  if (fs.existsSync(p)) fs.unlinkSync(p);
});
if (fs.existsSync(path.join(__dirname, 'prisma/migrations'))) {
  fs.rmSync(path.join(__dirname, 'prisma/migrations'), { recursive: true, force: true });
}

console.log('2. Gravando .env e prisma/schema.prisma em UTF-8 puro (Buffer sem BOM)...');
const envContent = 'DATABASE_URL="file:./dev.db"\n';
fs.writeFileSync(path.join(__dirname, '.env'), Buffer.from(envContent, 'utf8'));

const schemaContent = [
  'generator client {',
  '  provider = "prisma-client-js"',
  '}',
  '',
  'datasource db {',
  '  provider = "sqlite"',
  '  url      = env("DATABASE_URL")',
  '}',
  '',
  'model BronzeIngestao {',
  '  id               String   @id @default(uuid())',
  '  origemArquivo    String',
  '  formatoOriginal  String',
  '  caminhoDataLake  String',
  '  payloadBruto     String',
  '  statusPipeline   String   @default("PROCESSADO_PARA_SILVER")',
  '  recebidoEm       DateTime @default(now())',
  '}',
  '',
  'model SilverCliente {',
  '  id                 String            @id @default(uuid())',
  '  cpf                String            @unique',
  '  nome               String',
  '  email              String            @unique',
  '  uf                 String',
  '  nivelFidelidade    String',
  '  saldoPontos        Int               @default(0)',
  '  pontosAExpirar     Int               @default(0)',
  '  canalAquisicao     String',
  '  atualizadoEm       DateTime          @updatedAt',
  '  interacoes         SilverInteracao[]',
  '  metricasGold       GoldAnaliseRetencao?',
  '}',
  '',
  'model SilverInteracao {',
  '  id             String        @id @default(uuid())',
  '  clienteId      String',
  '  divisao        String',
  '  tipoAcao       String',
  '  valorGasto     Float         @default(0.0)',
  '  rota           String?',
  '  avaliacaoNPS   Int?',
  '  dataInteracao  DateTime      @default(now())',
  '  cliente        SilverCliente @relation(fields: [clienteId], references: [id], onDelete: Cascade)',
  '}',
  '',
  'model GoldAnaliseRetencao {',
  '  id                   String        @id @default(uuid())',
  '  clienteId            String        @unique',
  '  statusRetencao       String',
  '  riscoChurnScore      Float',
  '  ltvTotalGasto        Float',
  '  divisaoPrincipal     String',
  '  divisaoCrossSell     String',
  '  acaoRecomendada      String',
  '  calculadoEm          DateTime      @default(now())',
  '  cliente              SilverCliente @relation(fields: [clienteId], references: [id], onDelete: Cascade)',
  '}'
].join('\n') + '\n';

fs.writeFileSync(path.join(__dirname, 'prisma/schema.prisma'), Buffer.from(schemaContent, 'utf8'));

console.log('3. Gerando Prisma Client...');
execSync('npx prisma generate', { stdio: 'inherit' });

console.log('4. Criando tabelas fisicas no SQLite (Bronze, Silver e Gold)...');
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function criarTabelasFisicas() {
  await prisma.$executeRawUnsafe(`
    CREATE TABLE IF NOT EXISTS "BronzeIngestao" (
      "id" TEXT NOT NULL PRIMARY KEY,
      "origemArquivo" TEXT NOT NULL,
      "formatoOriginal" TEXT NOT NULL,
      "caminhoDataLake" TEXT NOT NULL,
      "payloadBruto" TEXT NOT NULL,
      "statusPipeline" TEXT NOT NULL DEFAULT 'PROCESSADO_PARA_SILVER',
      "recebidoEm" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
  `);

  await prisma.$executeRawUnsafe(`
    CREATE TABLE IF NOT EXISTS "SilverCliente" (
      "id" TEXT NOT NULL PRIMARY KEY,
      "cpf" TEXT NOT NULL,
      "nome" TEXT NOT NULL,
      "email" TEXT NOT NULL,
      "uf" TEXT NOT NULL,
      "nivelFidelidade" TEXT NOT NULL,
      "saldoPontos" INTEGER NOT NULL DEFAULT 0,
      "pontosAExpirar" INTEGER NOT NULL DEFAULT 0,
      "canalAquisicao" TEXT NOT NULL,
      "atualizadoEm" DATETIME NOT NULL
    );
  `);

  await prisma.$executeRawUnsafe(`CREATE UNIQUE INDEX IF NOT EXISTS "SilverCliente_cpf_key" ON "SilverCliente"("cpf");`);
  await prisma.$executeRawUnsafe(`CREATE UNIQUE INDEX IF NOT EXISTS "SilverCliente_email_key" ON "SilverCliente"("email");`);

  await prisma.$executeRawUnsafe(`
    CREATE TABLE IF NOT EXISTS "SilverInteracao" (
      "id" TEXT NOT NULL PRIMARY KEY,
      "clienteId" TEXT NOT NULL,
      "divisao" TEXT NOT NULL,
      "tipoAcao" TEXT NOT NULL,
      "valorGasto" REAL NOT NULL DEFAULT 0.0,
      "rota" TEXT,
      "avaliacaoNPS" INTEGER,
      "dataInteracao" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT "SilverInteracao_clienteId_fkey" FOREIGN KEY ("clienteId") REFERENCES "SilverCliente" ("id") ON DELETE CASCADE ON UPDATE CASCADE
    );
  `);

  await prisma.$executeRawUnsafe(`
    CREATE TABLE IF NOT EXISTS "GoldAnaliseRetencao" (
      "id" TEXT NOT NULL PRIMARY KEY,
      "clienteId" TEXT NOT NULL,
      "statusRetencao" TEXT NOT NULL,
      "riscoChurnScore" REAL NOT NULL,
      "ltvTotalGasto" REAL NOT NULL,
      "divisaoPrincipal" TEXT NOT NULL,
      "divisaoCrossSell" TEXT NOT NULL,
      "acaoRecomendada" TEXT NOT NULL,
      "calculadoEm" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT "GoldAnaliseRetencao_clienteId_fkey" FOREIGN KEY ("clienteId") REFERENCES "SilverCliente" ("id") ON DELETE CASCADE ON UPDATE CASCADE
    );
  `);

  await prisma.$executeRawUnsafe(`CREATE UNIQUE INDEX IF NOT EXISTS "GoldAnaliseRetencao_clienteId_key" ON "GoldAnaliseRetencao"("clienteId");`);
  await prisma.$disconnect();
  console.log('Tabelas BronzeIngestao, SilverCliente, SilverInteracao e GoldAnaliseRetencao criadas com sucesso!');
}

criarTabelasFisicas().then(() => {
  console.log('\n5. Populando Data Lake com dados sinteticos (seed.js)...');
  execSync('node prisma/seed.js', { stdio: 'inherit' });

  console.log('\n6. Executando teste final de Ingestao e Exportacao (test-final.js)...');
  execSync('node test-final.js', { stdio: 'inherit' });
});