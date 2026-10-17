const { processarEntradaUniversal } = require('./src/services/ingestService');
const prisma = require('./src/config/prisma');

async function testarEntradas() {
  console.log('--- TESTE 1: Enviando Texto Livre Desestruturado ---');
  const textoSolto = "Olá, sou cliente da Azul Viagens, meu email é maria.silva@teste.com e CPF 123.456.789-99. Quero fazer uma reclamação sobre meu pacote pois penso em cancelar!";
  
  const resTexto = await processarEntradaUniversal({ body: textoSolto });
  console.log('Resultado Texto Livre:', resTexto);

  console.log('\n--- TESTE 2: Enviando Objeto JSON Estruturado ---');
  const jsonEstruturado = [
    { nome: "Carlos Cargo", email: "carlos@empresa.com", cpf: "99988877766", regiao: "PE", divisao: "AZUL_CARGO", valorGasto: 3200 }
  ];

  const resJson = await processarEntradaUniversal({ body: jsonEstruturado });
  console.log('Resultado JSON:', resJson);

  const clienteExtraido = await prisma.cliente.findUnique({ where: { cpf: '12345678999' } });
  console.log('\nCliente salvo no banco a partir do texto livre:');
  console.log(clienteExtraido);
}

testarEntradas()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
