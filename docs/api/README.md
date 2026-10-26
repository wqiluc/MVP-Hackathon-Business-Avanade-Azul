# API HTTP do CRM de Alto Valor

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
OpenAPI. Eles existem por compatibilidade; novos consumidores devem usar as
rotas canônicas acima.

## Autenticação e erros

`POST /auth/login` é público. As demais rotas da tabela exigem token de sessão
no cabeçalho `Authorization: Bearer <token>`. O frontend armazena a sessão na
aba atual e encerra a sessão quando a API responde `401`. Credenciais
administrativas e de demonstração são configuradas no backend; não há
credenciais padrão a assumir.

Erros seguem o envelope da API com `success: false`, código, mensagem,
detalhes, status e caminho. Credenciais inválidas retornam `401`; upload com
conteúdo inválido retorna erro de validação; limite de admissão excedido pode
retornar `429` com `Retry-After`; indisponibilidade do limitador retorna `503`.
Os detalhes de configuração e políticas de erro estão em
[backend/README.md](../../backend/README.md).

## Upload e modelo

O endpoint canônico de upload aceita multipart no campo `arquivo` e o contrato
CSV atual, documentado em [dados e ingestão](../data/README.md). O alias
`/ingestao/ingest` preserva o contrato de resposta legado, mas não substitui
nem relaxa o contrato canônico.

`GET /modelo` consulta o alias `champion` no Model Registry quando configurado.
Sem modelo registrado, informa estado de espera; sem MLflow configurado no
desenvolvimento local, pode informar `aguardando-configuracao`. A rota de treino
é administrativa. Erros de validação de treino são convertidos em HTTP 400 e
falhas de execução/registro em HTTP 500. O logging do modelo sklearn permite
explicitamente o tipo de árvore necessário ao RandomForest do projeto. Tracking
e Serving são serviços separados, e os testes locais não comprovam
disponibilidade remota.

## Rate limiting de IA

As rotas de recomendação e análise passam pela admissão configurada por
`AI_RATE_LIMIT_*`. Em produção, Redis é obrigatório quando a admissão está
habilitada; indisponibilidade falha de forma fechada. Esse limite é orçamento
por janela da aplicação, não cota global do provedor. OpenAI e Gemini são
selecionados somente no backend por `LLM_PROVIDER`; fallback entre providers
é desabilitado por padrão e exige `LLM_FALLBACK_PROVIDER` explícito. Consulte o
[detalhamento e smoke test real](../../backend/README.md).

## Testes

Os testes de API fazem parte da suíte do backend. A integração de MLflow com
Tracking/Registry/Serving e a integração Snowflake são opt-in e requerem
ambiente isolado. Testes com mocks validam contratos e orquestração local, não
conectividade de serviços externos.
