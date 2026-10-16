const http = require('http');

const PORT = 5173;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="UTF-8">
      <title>AeroShield AI — Frontend Placeholder</title>
      <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; height: 100vh; align-items: center; justify-content: center; margin: 0; }
        .card { background: #1e293b; padding: 2.5rem; border-radius: 12px; border: 1px solid #334155; max-width: 500px; text-align: center; }
        h1 { color: #38bdf8; margin-top: 0; }
        a { color: #38bdf8; text-decoration: none; font-weight: bold; }
        .status { background: #065f46; color: #34d399; padding: 0.5rem 1rem; border-radius: 6px; display: inline-block; margin-top: 1rem; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>🚀 AeroShield AI — CRM Azul</h1>
        <p>O <strong>Backend FastAPI BFA</strong> está rodando com sucesso!</p>
        <p>Acesse a documentação interativa para testar os endpoints da solução:</p>
        <p><a href="http://localhost:8000/docs" target="_blank">http://localhost:8000/docs</a></p>
        <div class="status">Aguardando integração com a interface do Frontend</div>
      </div>
    </body>
    </html>
  `);
});

server.listen(PORT, () => {
  console.log(`\x1b[36m🎨 [Frontend Placeholder] Servidor visual rodando em: http://localhost:${PORT}\x1b[0m`);
});
