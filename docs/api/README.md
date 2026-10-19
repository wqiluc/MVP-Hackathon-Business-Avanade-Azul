# API HTTP

Base versionada: `/api/v1`. As rotas protegidas exigem `Authorization: Bearer
<token>`. `POST /auth/login` é público. O frontend usa a base configurada por
`VITE_API_URL`, por exemplo `http://localhost:8000/api/v1`.

| Método | Rota | Acesso | Serviço |
|---|---|---|---|
| POST | `/auth/login` | Público | Emissão de sessão/JWT |
| POST | `/ingestao/clientes` | Autenticado | Upload e ingestão de clientes |
| POST | `/ingestao/ingest` | Autenticado | Upload legado com resposta `UploadResponse` |
| GET | `/dashboard/resumo` | Autenticado | Resumo CRM |
| GET | `/clientes` | Autenticado | Lista de clientes |
| GET | `/clientes/{cliente_id}` | Autenticado | Detalhe do cliente |
| POST | `/clientes/{cliente_id}/recomendacao` | Autenticado | Recomendação |
| POST | `/clientes/analyze` | Autenticado | Análise por workflow de agentes |
| GET | `/modelo` | Autenticado | Modelo ativo pelo alias `champion` ou estado `aguardando-registro`. |
| POST | `/modelo/train` | Autenticado | Treino, métricas e registro MLflow |
| GET | `/health/` | Público | Healthcheck |

Aliases legados `/data`, `/ai` e `/ml` continuam registrados fora do schema
OpenAPI. A rota de treinamento converte erros de validação para HTTP 400 e
falhas de execução/registro em HTTP 500. O logging sklearn foi ajustado com
allowlist explícita para `sklearn.tree._tree.Tree`. O teste de integração
validou o fluxo de Tracking, Registry, alias `champion` e MLflow Serving.
Serving é um processo separado e não está necessariamente ativo localmente.
O endpoint `/modelo` consulta o Model Registry pelo alias `champion` e retorna
as informações do modelo ativo quando há uma versão registrada e disponível;
se ainda não houver modelo registrado, retorna o estado
`aguardando-registro`.
