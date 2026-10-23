# CRM de Alto Valor

CRM de Alto Valor é um MVP para apoiar equipes de relacionamento na
identificação de clientes prioritários e na preparação de ações de retenção.
O sistema reúne ingestão de dados, indicadores, classificação de risco baseada
em um target proxy e recomendações com revisão humana.

## Problema e proposta de valor

Equipes de CRM precisam priorizar o atendimento a partir de dados de clientes,
entender os sinais associados ao risco e organizar ações coerentes. O MVP
integra esses passos em uma interface única: a equipe carrega uma base,
consulta segmentos e perfis e avalia recomendações antes de aprová-las.

## Objetivo e limites do MVP

O objetivo é demonstrar um fluxo end-to-end localizável e auditável, da
ingestão ao apoio à decisão. O score atual classifica `high_risk_flag`, um
target proxy derivado de regras sobre incidentes e recência; não representa
churn observado nem uma probabilidade calibrada de evasão. A exposição
financeira exibida pelo workflow também é uma heurística, não uma previsão
financeira.

Este repositório não comprova prontidão de produção, disponibilidade de
serviços externos ou conformidade legal. Snowflake, MLflow remoto/Serving,
OpenAI e Gemini dependem de serviços e credenciais configurados fora do projeto. O
contexto de grafo é local e estático; não existe recuperação vetorial conectada.

## Arquitetura resumida

```text
React + Vite
    -> FastAPI (API, autenticação e orquestração)
        -> serviços de aplicação
            -> ingestão e camadas Bronze / Silver / Gold
            -> modelo de risco e MLflow Tracking / Serving
            -> workflow de agentes e contexto em grafo
            -> OpenAI/Gemini opcionais no backend, com fallback por regras
        -> recomendação apresentada ao analista para revisão humana
```

O backend é o orquestrador. O frontend não chama provedores de IA diretamente
e não deve receber segredos de provedores. DuckDB é a opção local; Snowflake é
uma integração externa configurável.

## Stack

- **Interface:** React, TypeScript, Vite, React Router e Recharts.
- **API e serviços:** Python, FastAPI e Pydantic.
- **Dados:** FileReader, DuckDB e adaptador Snowflake; camadas Bronze, Silver
  e Gold.
- **Machine learning:** scikit-learn, MLflow Tracking, Model Registry e
  Serving configurável.
- **Workflow de decisão:** LangGraph, regras determinísticas e grafo NetworkX
  estático; OpenAI ou Gemini opcionais para personalizar texto no backend.
- **Testes:** pytest, testes de serviço do frontend, lint e build.

## Estrutura do monorepo

```text
.
├── ai/              # workflow de agentes, contexto de grafo e helper local
├── backend/         # API FastAPI, serviços, schemas e testes
├── data/            # ingestão, camadas medallion e adapters
├── docs/            # arquitetura, API, dados, ML e IA
├── frontend/        # aplicação React + TypeScript + Vite
├── infrastructure/  # scripts SQL e guias operacionais de integrações
├── ml/              # features, treino, avaliação, inferência e Tracking
├── scripts/         # ferramentas de desenvolvimento, incluindo fixture CSV
├── package.json     # comandos de desenvolvimento do monorepo
├── pyproject.toml   # configuração dos pacotes Python
└── setup.js         # preparação e execução local
```

## Fluxo de dados

1. A API recebe o arquivo e valida o contrato canônico:
   `id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes`.
2. O serviço de ingestão pseudonimiza IDs com HMAC antes da persistência.
3. O pipeline materializa Bronze, transforma Silver e calcula Gold.
4. Quando o modelo está configurado, o score é calculado pelo MLflow Serving e
   persistido em Gold; sem modelo configurado, o score permanece nulo.
5. A API publica o resultado do upload e disponibiliza os dados para dashboard,
   lista, perfil e recomendação.

O upload substitui a base atual, não adiciona um histórico. O backend valida e
publica snapshots; a recuperação coberta é rollback antes da publicação
bem-sucedida, não restauração de versões históricas. O gerador de CSV sintético
em `scripts/` é apenas uma ferramenta de desenvolvimento e não integra a UI.

## Modelo de risco

O conjunto de treino usa `frequency`, `recency_days`, `total_spend`,
`flight_incidents` e `avg_ticket`, com `high_risk_flag` como target. O target é
uma regra proxy (`flight_incidents >= 2` ou `recency_days > 60`); métricas
descrevem a classificação dessa regra, não churn observado. Modelo, features,
target e métricas estão detalhados em [docs/ml/README.md](docs/ml/README.md).

## IA e recomendações

O Decision Agent seleciona ações por regras determinísticas e contexto de um
grafo pequeno, estático e definido no código. OpenAI ou Gemini, quando
habilitados, podem personalizar o texto da recomendação pelo backend, mas não
substituem a ação decidida. Sem configuração, o backend usa fallback
determinístico; na falha do provider, só tenta outro se
`LLM_FALLBACK_PROVIDER` estiver explicitamente configurado. Se todos falharem,
usa fallback determinístico e identifica a origem da resposta. As recomendações requerem
revisão humana; não são aconselhamento jurídico nem oferta confirmada. Veja
[docs/ai/README.md](docs/ai/README.md).

## Segurança e privacidade técnica

IDs de origem são pseudonimizados com HMAC-SHA256 antes da persistência;
pseudonimização não é anonimização. A chave `JWT_SECRET_KEY` também sustenta a
autenticação e sua rotação requer migração coordenada para preservar IDs.
Credenciais locais pertencem a `backend/.env`, que não deve ser versionado.
Chaves de provedores devem permanecer no backend; não as configure em variáveis
`VITE_*`. Antes de qualquer uso produtivo são necessárias revisões de segurança,
governança, privacidade, operação e disponibilidade do ambiente.

## Requisitos e configuração

- Node.js 20.19+ na linha 20 ou 22.12+ (recomendado: 24 LTS) e npm.
- Python 3.12+.
- Para desenvolvimento local, DuckDB e LLM desabilitado são os defaults
  recomendados. MLflow local é opcional; Snowflake, Redis, OpenAI e Gemini
  exigem configuração e serviços externos próprios.

Copie `backend/.env.example` para `backend/.env` somente se o arquivo local
ainda não existir. Configure uma conta local, gere uma `JWT_SECRET_KEY`
aleatória e persistente e mantenha credenciais fora do controle de versão. Para
detalhes de cada serviço, consulte [backend/README.md](backend/README.md),
[docs/architecture/README.md](docs/architecture/README.md) e os guias
específicos em `infrastructure/`.

## Execução local

Na raiz:

```bash
npm start
```

O script prepara os ambientes e inicia API e interface. A API fica em
`http://localhost:8000`, a documentação interativa em
`http://localhost:8000/docs` e o frontend em `http://localhost:5173`.
Configurações locais existentes não devem ser sobrescritas automaticamente.

## Testes e qualidade

Backend, a partir da raiz:

```bash
cd backend
SNOWFLAKE_INTEGRATION_TESTS=0 MLFLOW_INTEGRATION_TESTS=0 \
  DATA_LAKE_BACKEND=duckdb MLFLOW_TRACKING_URI= MLFLOW_SERVING_URL= \
  LLM_PROVIDER=disabled OPENAI_API_KEY= \
  .venv/bin/python -m pytest -q -p no:cacheprovider
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Testes de integração real com Snowflake, MLflow/Serving e Redis são opt-in,
dependem de ambientes isolados e não são substituídos por testes com mocks.
Consulte [docs/api/README.md](docs/api/README.md) e os guias de infraestrutura
antes de executar integrações reais.

## Documentação complementar

- [Arquitetura](docs/architecture/README.md)
- [API](docs/api/README.md)
- [Dados e ingestão](docs/data/README.md)
- [Machine learning e MLflow](docs/ml/README.md)
- [Workflow de IA](docs/ai/README.md)
- [Backend](backend/README.md)
- [Frontend](frontend/README.md)
- [Snowflake](infrastructure/snowflake/README.md)
- [MLflow](infrastructure/mlflow/README.md)

## Limitações atuais

- O target de risco é proxy, não churn observado.
- O grafo é estático e não existe recuperação vetorial/documental conectada.
- OpenAI e Gemini são opcionais; a ação é determinada pelo backend e a
  recomendação exige decisão humana.
- Snowflake e MLflow Serving dependem de infraestrutura externa e validação
  real no ambiente de destino.
- O upload substitui o snapshot atual; não há histórico de snapshots ou
  restauração de uma versão anterior pelo produto.
- O MVP não declara certificação de conformidade nem prontidão para produção.

## Próximos passos

O roadmap depende de validação e priorização do produto: validar dados e
resultados com especialistas de CRM; validar integrações e controles no
ambiente de destino; avaliar fontes documentais e contexto de políticas antes
de evoluir RAG; e definir observabilidade, governança, retenção e recuperação
operacional antes de qualquer implantação produtiva.
