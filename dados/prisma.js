const snowflake = require('snowflake-sdk');
require('dotenv').config();

const connectionPool = snowflake.createPool({
  account: process.env.SNOWFLAKE_ACCOUNT,
  username: process.env.SNOWFLAKE_USER,
  password: process.env.SNOWFLAKE_PASSWORD,
  database: process.env.SNOWFLAKE_DATABASE,
  warehouse: process.env.SNOWFLAKE_WAREHOUSE,
  role: process.env.SNOWFLAKE_ROLE
}, {
  max: 10,
  min: 2
});

function executeQuery(sqlText, binds = []) {
  return new Promise((resolve, reject) => {
    connectionPool.use(async (clientConnection) => {
      clientConnection.execute({
        sqlText,
        binds,
        complete: (err, stmt, rows) => {
          if (err) return reject(err);
          resolve(rows);
        }
      });
    }).catch(reject);
  });
}

module.exports = { executeQuery };