# IA, workflow de decisão e limitações

- `ai/agents/workflow.py` implementa o workflow LangGraph. Seus estágios
  calculam exposição monetária heurística (`total_spend × 1.30 × churn_score`),
  solicitam contexto do grafo, escolhem a ação por regras e definem um marcador
  de auditoria. O valor monetário não é uma estimativa financeira calibrada.
- `ai/graphrag/context_retrieval.py` consulta um grafo NetworkX pequeno,
  estático e definido no código. Não é um GraphRAG completo e não consulta uma
  fonte externa de políticas.
- O `AgentState` transporta `churn_score` (sem score concorrente), tier,
  frequência, gasto, incidentes, tipo de incidente, exposição, contexto,
  decisão e estado do workflow. A rota de CRM usa `churn_risk` apenas como alias
  legado na resposta pública.
- O Decision Agent usa score, tier, exposição, incidentes e contexto. Um
  incidente tipado com contagem positiva ou pelo menos dois incidentes conduz
  a revisão humana. Relações e estado de verificação do contexto influenciam
  evidências e texto/estratégia. O grafo é ilustrativo e não confirma regras
  vigentes ou elegibilidade.
- `ai/rag/embeddings.py` mantém o helper local de embeddings, mas ele não está
  conectado a um vector store ou ao workflow.

O Decision Agent continua determinístico. Depois da decisão, o serviço de CRM
pode chamar OpenAI ou Gemini no backend para personalizar texto estruturado,
sem permitir que o LLM substitua a ação decidida. Os providers compartilham o
contrato de resposta e recebem apenas atributos permitidos de perfil, score,
incidentes e contexto; não recebem identificador, nome, e-mail, CPF ou dataset.
Há timeout; somente rate limits temporários da OpenAI têm até três tentativas
totais, backoff exponencial e respeito ao cabeçalho `Retry-After`. Gemini não
tem retry automático. Quota/billing, timeout, conexão e erros permanentes da API
não entram em retry. Sem configuração ou com `LLM_PROVIDER=disabled`, usa
regras (`origem=regras`); falha de todos os providers configurados, incluindo
resposta estruturada inválida, usa regras com `origem=llm-indisponivel`;
resposta validada por qualquer provider usa `origem=llm`. Um provider
alternativo só é tentado se `LLM_FALLBACK_PROVIDER` for explicitamente
configurado. Logs registram somente a categoria técnica, sem payload, chave ou
dados do cliente.

RAG e GraphRAG permanecem limitados ao escopo demonstrativo do MVP: não há
pipeline documental, embeddings conectados, ChromaDB ou recuperação vetorial.
As recomendações não constituem aconselhamento jurídico nem oferta confirmada.

## Componentes e fronteiras

- **Agentes:** o workflow LangGraph coordena cálculo, recuperação de contexto,
  decisão por regras e conclusão. A resposta da API expõe a origem do texto
  (`regras`, `llm` ou `llm-indisponivel`) sem transferir ao LLM a decisão.
- **Contexto:** `ai/graphrag/context_retrieval.py` percorre relações de um
  grafo NetworkX pequeno e definido no código. O nome GraphRAG é histórico e
  não significa que haja ingestão documental ou GraphRAG completo.
- **Embeddings:** `ai/rag/embeddings.py` é um helper opcional local; não há
  indexação, vector store nem conexão desse helper com o workflow.
- **Provedor:** OpenAI e Gemini são integrações opcionais do serviço backend,
  resolvidas por uma camada comum. OpenAI tem retries limitados para rate
  limits temporários; Gemini não é repetido automaticamente. O fallback para
  outro provider só ocorre quando `LLM_FALLBACK_PROVIDER` o seleciona
  explicitamente. Nenhuma credencial ou chamada de provider deve ser colocada
  no frontend.

O workflow de agentes não executa ações externas nem realiza chamadas externas
por conta própria: ele calcula, recupera contexto e decide por regras dentro do
fluxo. A personalização textual via OpenAI ou Gemini ocorre posteriormente e
não transforma o workflow em um executor de ações externas.

Regras vigentes, elegibilidade e políticas não são confirmadas pelo grafo
ilustrativo. As ações/recomendações exigem revisão humana e devem ser avaliadas
com os responsáveis de negócio antes de qualquer uso operacional.
