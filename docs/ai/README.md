# AI atual e limitações

- `ai/agents/workflow.py` implementa o workflow LangGraph: calcula exposição
  monetária heurística (`total_spend × 1.30 × churn_score`), recupera contexto,
  toma uma decisão determinística e marca a conclusão do workflow. O valor
  monetário não é uma estimativa financeira calibrada.
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
pode chamar OpenAI no backend para personalizar texto estruturado, sem permitir
que o LLM substitua a ação decidida. A chamada usa apenas atributos de perfil,
score, incidentes e contexto; não envia identificador, nome, e-mail, CPF ou
dataset. Há timeout; rate limits temporários têm no máximo três tentativas
totais, backoff exponencial e respeito ao cabeçalho `Retry-After`. Quota/billing,
timeout, conexão e erros permanentes da API não entram em retry. Sem chave ou
com `LLM_PROVIDER=disabled`, usa regras (`origem=regras`); falha na chamada,
incluindo resposta estruturada inválida, usa o fallback com
`origem=llm-indisponivel`; resposta validada usa `origem=llm`. Logs registram
somente a categoria técnica, sem payload, chave ou dados do cliente.

RAG e GraphRAG permanecem limitados ao escopo demonstrativo do MVP: não há
pipeline documental, embeddings conectados, ChromaDB ou recuperação vetorial.
As recomendações não constituem aconselhamento jurídico nem oferta confirmada.
