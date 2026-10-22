<h1 align="center">Hackathon Business Azul & Avanade <br>
<img src="./img/Azul logo.jpg" alt="Logo Azul" width="490"></h1>
</br>

<p align="center">
  <b>Plataforma Preditiva BFA (Backend for Agents) para Preservação de LTV e Gestão de Churn no CRM Azul (Alto Valor)</b>
</p>

<h2 align="center" id="integrantes">👤👨‍🎓 Integrantes do Projeto: </h2>

<ul>
<li>Gabriel Meiki Maeda Taira <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Gustavo Geraldo Campos da Silva <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Julia Santos <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Lucas Paguetti Pereira <a href="https://www.linkedin.com/in/lucas-paguetti-pereira" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="https://github.com/wqiluc" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Lucas Rodrigues Meza <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
</ul>

<h2 align="center" id="tecnologias"> ⛏️💻 Tecnologias Utilizadas: <br>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
<img src="https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
<img src="https://img.shields.io/badge/DuckDB-FFF000?style=for-the-badge&logo=duckdb&logoColor=black" alt="DuckDB"/>
<img src="https://img.shields.io/badge/MLflow-0194E2?style=for-the-badge&logo=mlflow&logoColor=white" alt="MLflow"/>
<img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangChain"/>
<img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
<img src="https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white" alt="Node.js"/>
</h2>

## 📌 Visão Geral do Projeto

O **CRM de Alto Valor Azul** é um protótipo para as equipes internas de operações e CRM. A aplicação organiza clientes, calcula o score do classificador `high_risk_flag` e demonstra recomendações de retenção usando regras determinísticas e, quando configurada, OpenAI no backend.

O fluxo de decisão usa LangGraph e um grafo NetworkX pequeno, estático e definido em código. O grafo fornece contexto ilustrativo; não há recuperação vetorial, embeddings conectados ou ChromaDB. O Decision Agent decide a ação, e OpenAI (se habilitada) personaliza o texto sem substituir a ação escolhida. Sem OpenAI ou quando a chamada falha, o backend usa regras e informa a origem da recomendação.

`high_risk_flag` é um target proxy construído por regra de incidentes/recência, não churn observado. `churn_score` é a saída do RandomForest treinado para esse proxy. Não interprete suas métricas como capacidade comprovada de prever churn real.

---

<h2 align="center" id="arquitetura">🏰 Arquitetura do Repositório (Monorepo) <br>
<img src="https://img.shields.io/badge/Architecture-111827?style=flat-square&logo=instructure&logoColor=white" height="22"/>
</h2>

O repositório é organizado no formato Monorepo para garantir coesão entre engenharia de dados, inteligência artificial e interface do analista:

```text
MVP-Hackathon-Business-Avanade-Azul/
├── package.json               # Script unificado para orquestração (npm start)
├── setup.js                   # Script universal de verificação e inicialização OS-agnóstico
├── README.md                  # Documentação global da Monorepo
│
├── ai/                        # Workflow de agentes e recuperação contextual em grafo
├── backend/                   # FastAPI, serviços, schemas e testes
├── data/                      # FileReader, Bronze, Silver, Gold e adaptador DuckDB
├── docs/                      # Arquitetura, API, Data, ML e AI
├── frontend/                  # Aplicação React + TypeScript + Vite
├── infrastructure/            # SQL versionado de MLflow e Snowflake
├── ml/                        # Features, inferência, treino, avaliação e MLflow
└── pyproject.toml             # Registro dos pacotes do monorepo
```

---

## ⚡ Guia de Execução Rápida

Disponibilizamos um orquestrador universal em Node.js (`setup.js`) que:

1. **Identifica automaticamente o Sistema Operacional** (Windows, Linux ou macOS).
2. **Valida a presença dos requisitos**: Python 3.12+ e Node.js compatível com Vite.
3. **Configura o ambiente isolado**: Cria o ambiente virtual Python (`backend/.venv`) e atualiza o `pip`.
4. **Gerencia dependências**: Instala requirements do Backend, registra o monorepo em modo editável e instala dependências npm do Frontend.
5. **Execução local**: Inicia Backend e Frontend; encerra os processos ao usar `CTRL+C`. Tracking só é iniciado quando explicitamente configurado para localhost. Serving é uma integração separada e opcional no desenvolvimento.

### 📋 Pré-requisitos
* **Node.js**: 20.19+ na linha 20 ou 22.12+ (recomendado: 24 LTS), e **npm**
* **Python**: 3.12+

### 🚀 Passo Único de Execução

Na raiz do repositório clonado, execute o seguinte comando no terminal:

```bash
npm start
```

Antes de iniciar, copie `backend/.env.example` para `backend/.env` apenas se o
arquivo ainda não existir. Configure uma conta local com `DEMO_EMAIL` e
`DEMO_PASSWORD` (ou `ADMIN_EMAIL` e `ADMIN_PASSWORD` para testar funções
administrativas). Não há credenciais de login padrão no backend.

Para desenvolvimento sem serviços externos, use `ENVIRONMENT=development`,
`DATA_LAKE_BACKEND=duckdb`, `LLM_PROVIDER=disabled`, `REDIS_URL=` e deixe
`MLFLOW_TRACKING_URI`, `MLFLOW_MODEL_NAME` e `MLFLOW_SERVING_URL` vazios.
Não altere arquivos locais existentes automaticamente. Gere uma
`JWT_SECRET_KEY` aleatória e persistente para manter sessões e pseudônimos entre
reinícios; sem ela, desenvolvimento usa uma chave efêmera por processo.
O frontend usa `VITE_API_URL=http://localhost:8000/api/v1`; nenhuma credencial
de provedor deve estar em `VITE_*`.

Sem modelo configurado, o upload local continua validando e publicando
Bronze/Silver/Gold no DuckDB; `churn_score` permanece nulo e a interface informa
que o score está indisponível. O upload substitui a base local inteira:
use somente dados de desenvolvimento. O gerador CSV em `scripts/` é ferramenta
de desenvolvimento, não um botão da interface de produção.

### Testes locais

```bash
cd backend
SNOWFLAKE_INTEGRATION_TESTS=0 MLFLOW_INTEGRATION_TESTS=0 \
  DATA_LAKE_BACKEND=duckdb MLFLOW_TRACKING_URI= MLFLOW_SERVING_URL= \
  LLM_PROVIDER=disabled OPENAI_API_KEY= \
  .venv/bin/python -m pytest -q -p no:cacheprovider
```

Em outro terminal: `cd frontend && npm test && npm run lint && npm run build`.
Os comandos acima usam sintaxe POSIX; no PowerShell, defina as mesmas variáveis
com `$env:NOME="valor"` antes de executar o Python.
As integrações reais são opt-in e não fazem parte do fluxo normal de testes.

### Integrações externas

| Integração | Configuração | Desenvolvimento local e indisponibilidade |
|---|---|---|
| Snowflake | `DATA_LAKE_BACKEND=snowflake`, `SNOWFLAKE_ACCOUNT/USER/PASSWORD/DATABASE/WAREHOUSE/ROLE` | Opcional; DuckDB é o default. Selecionar Snowflake exige conta/permissões provisionadas; falhas não trocam silenciosamente de backend. |
| MLflow | `MLFLOW_TRACKING_URI`, `MLFLOW_MODEL_NAME`, `MLFLOW_SERVING_URL` | Opcional; nome exato do Registry vem do ambiente, alias `champion`. Sem Tracking/nome, não consulta modelo e não inventa métricas ou scores. Uma integração configurada, mas indisponível, sinaliza erro; readiness verifica os endpoints configurados. |
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` | Opcional, só no backend. Sem configuração usa `regras`; falha do provedor usa `llm-indisponivel`. |
| Redis | `REDIS_URL`, `AI_RATE_LIMIT_*` | Sem URL, development/test usa limitador em memória por processo. Produção exige Redis quando o limitador está ativo e falha de forma fechada. |

Chroma/recuperação vetorial e GraphRAG externo não estão conectados: o grafo
atual é estático e local, sem serviço adicional obrigatório.

O E2E real depende de infraestrutura externa previamente provisionada e não é
executado no fluxo normal de desenvolvimento local. O teste Snowflake exige
`SNOWFLAKE_INTEGRATION_TESTS=1` e
`SNOWFLAKE_TEST_DATABASE=CRM_TEST_E2E`, além de MLflow configurado. O bootstrap
atual ainda executa `CREATE DATABASE IF NOT EXISTS`; um database pré-criado não
dispensa validar esse requisito de permissão. Não execute com a role sem
permissão/autorização e nunca use `AZUL_DATA_LAKE` como destino E2E.

## 🌐 Serviços Disponibilizados Após Inicialização

| Serviço | Endereço Local | Descrição |
| :--- | :--- | :--- |
| **🎨 Frontend Dashboard** | [http://localhost:5173](http://localhost:5173) | Painel operacional do analista de CRM Azul |
| **⚡ Backend FastAPI BFA** | [http://localhost:8000](http://localhost:8000) | Motor de APIs, Data Lake e orquestração de IA |
| **📄 Swagger UI Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Documentação interativa e especificação OpenAPI |
| **📈 MLflow Tracking (opcional)** | [http://localhost:5000](http://localhost:5000) | Somente quando explicitamente habilitado; disponibilidade depende do ambiente |
| **❄️ Snowflake Data Lake (externo)** | Conta configurada | Não iniciado no desenvolvimento padrão |

---

O pipeline integrado seleciona `Snowflake` com `DATA_LAKE_BACKEND=snowflake`;
DuckDB permanece disponível para desenvolvimento local/offline. Snowflake
precisa de credenciais, permissões e database configurados em `backend/.env`.
O backend cria os schemas de camada e executa o SQL versionado em
[`infrastructure/snowflake/README.md`](infrastructure/snowflake/README.md).
Snowflake não é iniciado pelo `setup.js` porque é um serviço externo.

O MLflow Serving pode ser habilitado separadamente em `http://localhost:5001`,
quando houver modelo registrado e autorização para essa integração. Consulte
[`infrastructure/mlflow/README.md`](infrastructure/mlflow/README.md) para os
comandos e configuração de inferência.

### Configuração LLM

Copie `backend/.env.example` para `backend/.env` e configure as credenciais
fora do frontend. `LLM_PROVIDER=openai` usa `OPENAI_API_KEY` no backend e o
modelo em `OPENAI_MODEL`. Com `LLM_PROVIDER=disabled` ou sem chave, a
recomendação continua funcionando por regras. Se uma chamada OpenAI falhar, a
resposta é marcada `llm-indisponivel` e usa o mesmo fallback determinístico.
Não envie chaves para variáveis `VITE_*`.

## 🛡️ Segurança e Conformidade LGPD

* **Identificadores**: análise e ingestão usam pseudônimos HMAC-SHA256 com separação de domínio e `JWT_SECRET_KEY`; o ID de origem não é persistido. Isso é pseudonimização, não anonimização nem garantia de conformidade legal. A rotação de `JWT_SECRET_KEY` muda os identificadores e exige migração coordenada. Revisão de governança e privacidade é necessária antes de uso produtivo.
* **Serviços externos**: Snowflake remoto, MLflow remoto/Serving e OpenAI dependem de credenciais, quotas e disponibilidade próprias. Testes locais não comprovam disponibilidade do ambiente externo configurado.