
# ⚡ Engine BFA & Arquitetura do Backend

> **Backend for Agents (BFA) orientado a eventos, MLOps e orquestração de IA Multiagente**  
> *Desenvolvido com FastAPI, Python 3.12, DuckDB (Medallion Data Lake), MLflow, ChromaDB e LangGraph.*

---

## 📐 Padrão Arquitetural

O Backend adota a **Modular Layered Architecture** (uma abordagem pragmática da *Clean Architecture* e *Domain-Driven Design*), onde cada diretório possui responsabilidade bem delimitada:

```text
backend/app/
├── api/                       # CAMADA DE APRESENTAÇÃO (Controllers / HTTP Routes)
│   ├── router.py              # Agregador central de rotas (/api/v1)
│   └── v1/
│       ├── auth.py            # Autenticação e emissão de tokens JWT
│       ├── health.py          # Liveness & Readiness Probes
│       ├── uploads.py         # Recebimento e validação de arquivos (.xlsx / .json)
│       ├── ml.py              # MLOps: Treinamento do modelo de risco e MLflow
│       └── clients.py         # Orquestração de BFA e Análise Preditiva de Clientes
│
├── core/                      # INFRAESTRUTURA & SEGURANÇA GLOBAL
│   ├── security.py            # Validação JWT, Hashing e Anonimização SHA-256
│   └── exceptions.py          # Centralização e tratamento global de erros HTTP/500
│
├── schemas/                   # CONTRATOS & DTOs (Pydantic Schemas)
│   ├── auth_schema.py         # Contratos de Login e Tokens
│   ├── upload_schema.py       # Contratos do Data Lake Medalhão
│   └── client_schema.py       # Contratos de Requisição/Resposta de Análise
│
└── services/                  # CAMADA DE DOMÍNIO & REGRAS DE NEGÓCIO
    ├── datalake_service.py    # Pipeline Medalhão em DuckDB (Bronze -> Silver -> Gold)
    ├── ml_service.py          # Treinamento de ML (RandomForest) e Tracking via MLflow
    ├── rag_service.py         # GraphRAG (ANAC Resolução 400 + Regras Azul Fidelidade)
    ├── agent_service.py       # Orquestrador de Estados LangGraph (Query, RAG, Decision, Audit)
    └── upload_service.py      # Gestão do ciclo de vida de arquivos temporários
```

---

## 🗄️ 1. Data Lake & Arquitetura Medalhão (`DataLakeService`)

O Data Lake local utiliza **DuckDB** como motor OLAP integrado, operando como um substituto local para ambientes Snowflake sem gerar custos.

### Camada Bronze — Raw

Ingestão direta de tabelas brutas fornecidas em arquivos:

- Excel (`.xlsx`)
- JSON

### Camada Prata — Silver / Cleaned

Responsável por:

- Limpeza de valores nulos.
- Padronização de tipos primitivos.
- Conversão de identificadores em hashes anonimizados.
- Formatação dos identificadores no padrão `AZ-XXXXXXXX`.
- Adequação para conformidade com a LGPD.

### Camada Ouro — Gold / Analytics & Feature Store

Tabela consolidada com cálculo de métricas agregadas, como:

- Ticket Médio.
- Frequência.
- Recência.
- Flags de Alto Risco.

Os dados dessa camada são consumidos diretamente pelo modelo de **Machine Learning** e pelos dashboards de **BI**.

---

## 📊 2. Esteira de MLOps (`MLflow` & `Scikit-Learn`)

A predição de **rotatividade (Churn)** e **risco de desengajamento do cliente** é realizada por um classificador treinado sobre a **Camada Ouro**.

### Métricas avaliadas

- **Acurácia:** meta ≥ 90%.
- **Precisão.**
- **Recall.**
- **F1-Score.**

### Tracking de experimentos

Todos os hiperparâmetros e binários do modelo são versionados e registrados através do **MLflow Tracking**.

Execução do pipeline de treinamento via API:

```http
POST /api/v1/ml/train
```

---

## 🕸️ 3. Engine de IA Multiagente

### BFA com LangGraph & GraphRAG

A orquestração utiliza o **LangGraph** para guiar o fluxo de decisão assíncrono através de quatro agentes especializados:

```text
[Input Analista]
       │
       ▼
(1. Query Manager Agent)
       │
       ▼
(2. GraphRAG Agent)
       │
       ▼
(3. Decision Engine)
       │
       ▼
(4. Audit Agent)
       │
       ▼
[Ação Aprovada]
```

### 1. Query Manager Agent

Responsável por:

- Avaliar métricas financeiras.
- Calcular o *Value-at-Risk (VaR)*.
- Classificar o Tier do passageiro.

### 2. GraphRAG Agent

Consulta a base de conhecimento estruturada em grafos de relacionamento, incluindo:

- **ANAC Resolução 400.**
- Regras do **Azul Fidelidade**.

O objetivo é fundamentar juridicamente as compensações e reduzir o risco de alucinações da IA.

### 3. Decision Engine Agent

Define estrategicamente o benefício de retenção.

Exemplo:

> Voucher Trust-First de R$ 250,00 + Upgrade Espaço Azul.

### 4. Audit Agent

Realiza a checagem antifraude das regras de elegibilidade antes da emissão do benefício.

---

## 🛠️ 4. Configuração de Variáveis de Ambiente (`.env`)

Crie o arquivo:

```text
backend/.env
```

com base no modelo:

```text
.env.example
```

Exemplo de configuração:

```ini
ENVIRONMENT=development

SECRET_KEY=sua_secret_key_hex_32_caracteres
JWT_SECRET_KEY=sua_jwt_secret_key_hex_32_caracteres

ACCESS_TOKEN_EXPIRE_HOURS=8

# Provedor de IA
# Modo gratuito/local via Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Caminhos do Data Lake
DUCKDB_PATH=../data/processed/azul_datalake.duckdb
VECTORDB_PATH=../data/vectordb
```

---

## 🔐 5. Como Gerar as Chaves Criptográficas Locais

No terminal, execute:

```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32)); print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
```

O comando irá gerar duas chaves aleatórias de 32 bytes:

```text
SECRET_KEY=...
JWT_SECRET_KEY=...
```

Copie os valores gerados para o arquivo `backend/.env`.

> ⚠️ **Importante:** nunca versione o arquivo `.env` no Git. Adicione-o ao `.gitignore`.

Exemplo:

```gitignore
.env
*.env
```

---

## 🧪 6. Testes Automatizados

A suíte de testes do backend valida:

- Autenticação.
- Processamento do Data Lake.
- Fluxo dos agentes.
- APIs.
- Regras de negócio.

Para executar os testes com **Pytest**:

```bash
pytest -v tests/test_backend.py
```

---

## 🚀 7. Execução do Backend

A partir do diretório `backend/`, ative o ambiente virtual:

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Depois, instale as dependências:

```bash
pip install -r requirements.txt
```

Execute a aplicação com:

```bash
uvicorn app.main:app --reload
```

O backend estará disponível em:

```text
http://localhost:8000
```

### Swagger / OpenAPI

A documentação interativa da API estará disponível em:

```text
http://localhost:8000/docs
```

### ReDoc

A documentação alternativa estará disponível em:

```text
http://localhost:8000/redoc
```

---

## 🏗️ 8. Fluxo Geral da Aplicação

```text
                    ┌─────────────────────┐
                    │     Frontend / BI    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     FastAPI API     │
                    │       /api/v1       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────────┐   ┌───────────┐
        │ Uploads  │    │   Clients    │   │    ML     │
        └────┬─────┘    └──────┬───────┘   └─────┬─────┘
             │                 │                  │
             ▼                 ▼                  ▼
        ┌────────────────────────────────────────────────┐
        │                  Services                       │
        │                                                │
        │ DataLake │ RAG │ Agents │ ML │ Upload         │
        └───────────────────────┬────────────────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              │                 │                  │
              ▼                 ▼                  ▼
        ┌───────────┐     ┌──────────┐      ┌──────────┐
        │  DuckDB   │     │ ChromaDB │      │ MLflow   │
        │ Data Lake │     │ GraphRAG │      │  MLOps   │
        └───────────┘     └──────────┘      └──────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │   Ollama     │
                         │     LLM      │
                         └──────────────┘
```

---

## 📁 9. Estrutura Completa do Projeto

```text
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   │
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── health.py
│   │       ├── uploads.py
│   │       ├── ml.py
│   │       └── clients.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py
│   │   └── exceptions.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth_schema.py
│   │   ├── upload_schema.py
│   │   └── client_schema.py
│   │
│   └── services/
│       ├── __init__.py
│       ├── datalake_service.py
│       ├── ml_service.py
│       ├── rag_service.py
│       ├── agent_service.py
│       └── upload_service.py
│
├── tests/
│   └── test_backend.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   │   └── azul_datalake.duckdb
│   └── vectordb/
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🎯 10. Objetivo Arquitetural

O backend foi projetado para demonstrar uma arquitetura moderna orientada a **IA, dados e agentes**, combinando:

- **FastAPI** para exposição das APIs.
- **Python 3.12** como linguagem principal.
- **DuckDB** para processamento analítico local.
- **Arquitetura Medallion** para organização do Data Lake.
- **Scikit-Learn** para Machine Learning.
- **MLflow** para MLOps e rastreamento de experimentos.
- **ChromaDB** para armazenamento vetorial.
- **GraphRAG** para recuperação contextual.
- **LangGraph** para orquestração multiagente.
- **Ollama** para execução local do LLM.
- **JWT** para autenticação.
- **SHA-256** para anonimização de identificadores.
- **FastAPI + Pydantic** para contratos e validação.

O resultado é um **Backend for Agents (BFA)** capaz de integrar dados estruturados, Machine Learning, RAG e agentes de IA em um fluxo de decisão auditável e orientado a regras de negócio.

