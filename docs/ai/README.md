# AI atual e limitações

- `ai/agents/workflow.py` implementa o workflow LangGraph e quatro estágios:
  classificação determinística de valor/risco, enriquecimento de contexto,
  decisão por regras e marcador de auditoria.
- `ai/graphrag/context_retrieval.py` consulta um grafo NetworkX pequeno,
  estático e definido no código. Não é um GraphRAG completo e não consulta uma
  fonte externa de políticas.
- `ai/rag/embeddings.py` mantém o helper local de embeddings, mas ele não está
  conectado a um vector store ou ao workflow.

Não há chamadas de LLM, prompts executados ou componentes em `ai/tools` e
`ai/workflows`. Essas capacidades continuam pendentes; recomendações atuais
são determinísticas e não constituem aconselhamento jurídico.
