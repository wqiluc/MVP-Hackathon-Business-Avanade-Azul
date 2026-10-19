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
├── pyproject.toml             # Registro dos pacotes do monorepo
└── setup.js                   # Ambiente Python/Node e inicialização local
```

---

## ⚡ Guia de Execução Rápida

Disponibilizamos um orquestrador universal em Node.js (`setup.js`) que:

1. **Identifica automaticamente o Sistema Operacional** (Windows, Linux ou macOS).
2. **Valida a presença dos requisitos**: Python 3.12+ e Node.js v18+.
3. **Configura o ambiente isolado**: Cria o ambiente virtual Python (`backend/.venv`) e atualiza o `pip`.
4. **Gerencia dependências**: Instala requirements do Backend, registra o monorepo em modo editável e instala dependências npm do Frontend.
5. **Execução integrada**: Inicia MLflow Tracking local (quando configurado para localhost), Backend e Frontend; encerra os processos ao usar `CTRL+C`. MLflow Serving é separado e deve ser iniciado após o primeiro modelo ser registrado.

### 📋 Pré-requisitos
* **Node.js**: v18+ e **npm**
* **Python**: 3.12+

### 🚀 Passo Único de Execução

Na raiz do repositório clonado, execute o seguinte comando no terminal:

```bash
npm start
```

## 🌐 Serviços Disponibilizados Após Inicialização

| Serviço | Endereço Local | Descrição |
| :--- | :--- | :--- |
| **🎨 Frontend Dashboard** | [http://localhost:5173](http://localhost:5173) | Painel operacional do analista de CRM Azul |
| **⚡ Backend FastAPI BFA** | [http://localhost:8000](http://localhost:8000) | Motor de APIs, Data Lake e orquestração de IA |
| **📄 Swagger UI Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Documentação interativa e especificação OpenAPI |
| **📈 MLflow Tracking** | [http://localhost:5000](http://localhost:5000) | Experimentos, runs, artefatos e Model Registry |
| **❄️ Snowflake Data Lake** | Conta configurada | Bronze, Silver e Gold na conta Snowflake configurada |

---

O pipeline integrado seleciona `Snowflake` com `DATA_LAKE_BACKEND=snowflake`;
DuckDB permanece disponível para desenvolvimento local/offline. Snowflake
precisa de credenciais, permissões e database configurados em `backend/.env`.
O backend cria os schemas de camada e executa o SQL versionado em
[`infrastructure/snowflake/README.md`](infrastructure/snowflake/README.md).
Snowflake não é iniciado pelo `setup.js` porque é um serviço externo.

O MLflow Serving é iniciado separadamente em `http://localhost:5001` depois do
treino inicial. Consulte
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