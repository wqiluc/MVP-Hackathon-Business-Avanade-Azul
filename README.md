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

O **AeroShield AI** é uma plataforma corporativa *Trust-First* projetada especificamente para as **equipes internas de operações e analistas de CRM da Azul Linhas Aéreas**. A aplicação monitora e prediz o risco de perda (churn) de passageiros VIP e de Alto Valor (*TudoAzul Topázio, Safira, Diamante e VIP World Legend*) expostos a incidentes de voo.

Antes mesmo de o passageiro formalizar uma reclamação, a plataforma calcula o **Risk Profile**, aciona uma rede de **Multiagentes LLM (LangGraph)** e sugere ações preventivas (vouchers de compensação imediata, upgrades para assentos Espaço Azul ou Executiva vacante) fundamentadas na **Resolução 400 da ANAC** e nas regras de negócio do programa de fidelidade.

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
├── data/                      # Data Lake e Persistência Local (Desconectado do código-fonte)
│   ├── raw/                   # Área de pouso temporária para arquivos em Excel e JSON
│   ├── processed/             # Banco DuckDB (Camadas Bronze, Silver e Gold da Arquitetura Medalhão)
│   └── vectordb/              # Base vetorial local (ChromaDB com HuggingFace Embeddings)
│
├── backend/                   # Engine BFA em FastAPI, Multiagentes (LangGraph) e MLOps (MLflow)
│   ├── run.py                 # Ponto de entrada do Uvicorn / FastAPI
│   ├── requirements.txt       # Dependências limpas e otimizadas em Python 3.12
│   ├── README.md              # Documentação técnica detalhada do Backend
│   └── app/                   # Clean Architecture em Camadas (api, core, schemas, services)
│
└── frontend/                  # Dashboard do Analista de Operações Azul
    ├── package.json           # Dependências e scripts do Frontend
    └── index.js               # Servidor visual de integração
```

---

## ⚡ Guia de Execução Rápida

Disponibilizamos um orquestrador universal em Node.js (`setup.js`) que:

1. **Identifica automaticamente o Sistema Operacional** (Windows, Linux ou macOS).
2. **Valida a presença dos requisitos**: Python 3.12+ e Node.js v18+.
3. **Configura o ambiente isolado**: Cria o ambiente virtual Python (`.venv`) e atualiza o `pip`.
4. **Gerencia dependências**: Instala automaticamente pacotes ausentes no Backend e Frontend.
5. **Execução paralela e limpa**: Inicia ambos os serviços simultaneamente com gerenciamento gracioso de processos (encerramento via `CTRL+C`).

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

---

## 🛡️ Segurança e Conformidade LGPD

* **Minimização de Dados (LGPD)**: Identificadores pessoais sensíveis de passageiros (CPF, Documento ou Nome) são criptografados de forma irrecuperável utilizando hashes SHA-256 (`AZ-XXXXXX`), atendendo estritamente ao princípio de anonimização da **Lei nº 13.709/2018**.