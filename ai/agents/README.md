# AI agents

`workflow.py` contém o workflow LangGraph atual. Os estágios calculam valor e
risco, solicitam contexto do grafo, escolhem benefícios usando regras fixas e
definem um marcador de auditoria. Não há chamadas a LLM nem execução de ações
externas.
