require('dotenv').config();
const snowflake = require('snowflake-sdk');

function getConnection() {
  return snowflake.createConnection({
    account: process.env.SNOWFLAKE_ACCOUNT,
    username: process.env.SNOWFLAKE_USER,
    password: process.env.SNOWFLAKE_PASSWORD,
    database: process.env.SNOWFLAKE_DATABASE,
    warehouse: process.env.SNOWFLAKE_WAREHOUSE,
    role: process.env.SNOWFLAKE_ROLE
  });
}

function executeQuery(sqlText, binds = []) {
  return new Promise((resolve, reject) => {
    const connection = getConnection();
    connection.connect((err, conn) => {
      if (err) return reject(err);

      conn.execute({
        sqlText,
        binds,
        complete: (err, stmt, rows) => {
          conn.destroy(); // Fecha a conexão após a query
          if (err) return reject(err);
          resolve(rows);
        }
      });
    });
  });
}

module.exports = { executeQuery };