require('dotenv').config();
const snowflake = require('snowflake-sdk');

console.log('Tentando conectar com os seguintes parâmetros:');
console.log({
  account: process.env.SNOWFLAKE_ACCOUNT,
  username: process.env.SNOWFLAKE_USER,
  database: process.env.SNOWFLAKE_DATABASE,
  warehouse: process.env.SNOWFLAKE_WAREHOUSE,
  role: process.env.SNOWFLAKE_ROLE
});

const connection = snowflake.createConnection({
  account: process.env.SNOWFLAKE_ACCOUNT,
  username: process.env.SNOWFLAKE_USER,
  password: process.env.SNOWFLAKE_PASSWORD,
  database: process.env.SNOWFLAKE_DATABASE,
  warehouse: process.env.SNOWFLAKE_WAREHOUSE,
  role: process.env.SNOWFLAKE_ROLE
});

connection.connect((err, conn) => {
  if (err) {
    console.error('\n❌ ERRO DETALHADO DO SNOWFLAKE:');
    console.error('Código:', err.code);
    console.error('Mensagem:', err.message);
    console.error('Detalhes:', err.data || err);
    return;
  }
  
  console.log('\n✅ Conexão estabelecida com sucesso!');
  
  conn.execute({
    sqlText: 'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_WAREHOUSE();',
    complete: (err, stmt, rows) => {
      if (err) {
        console.error('Erro na query de teste:', err.message);
      } else {
        console.log('Contexto da Sessão:', rows);
      }
      conn.destroy();
    }
  });
});