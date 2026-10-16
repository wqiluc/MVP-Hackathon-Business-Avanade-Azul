<h1 align="center">Hackathon Business - Azul - CRM Alto Valor <br>
<img src="./img/Azul logo.jpg" alt="Logo Azul" width="490"></h1>

<h2 align="center" id="integrantes">👤👨‍🎓 Integrantes do Projeto: </h2>
<ul>
<li>Gabriel Meiki Maeda Taira <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Gustavo Geraldo Campos da Silva <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Julia Santos <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Lucas Paguetti Pereira <a href="https://www.linkedin.com/in/lucas-paguetti-pereira" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="https://github.com/wqiluc" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
<li>Lucas Rodrigues Meza <a href="" target="_blank"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" width="14"/></a> <a href="" target="_blank"><img src="https://img.shields.io/badge/GitHub-000000?style=for-the-badge&logo=github&logoColor=white" height="16"/></a></li>
</ul>

> 🔒 **Repositório privado.** O enunciado do desafio é confidencial; não publique este conteúdo.

<h2 align="center" id="sobre">🎯 Sobre o Projeto</h2>

**CRM de Alto Valor** é uma ferramenta **interna, para as equipes de CRM, Fidelidade e Relacionamento da Azul** (não para os passageiros). Ela ajuda essas equipes a:

- **Identificar** os clientes de alto valor com um score que combina valor monetário, frequência, recência e potencial futuro (CLV);
- **Antecipar** o risco de evasão com um modelo de machine learning explicável;
- **Agir** com uma recomendação personalizada por cliente, redigida por IA generativa e aprovada por um analista antes de qualquer envio.

Como não há acesso a dados reais, toda a solução roda sobre uma **base sintética** calibrada por fontes públicas (ANAC, RI da Azul, regulamento do Azul Fidelidade e avaliações públicas). A arquitetura foi desenhada para que essa base possa ser trocada por dados reais **sem reconstruir a solução**.

<h2 align="center" id="tecnologias"> ⛏️💻 Tecnologias Utilizadas: <br>
<img src="https://img.shields.io/badge/Tech_Stack-111827?style=for-the-badge&logo=stackshare&logoColor=white" alt="Tecnologias Badge"/>
</h2>

<p align="center">
<img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB"/>
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white"/>
<img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white"/>
<img src="https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white"/>
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/MLflow-0194E2?style=for-the-badge&logo=mlflow&logoColor=white"/>
</p>

| Camada | Tecnologia | Status |
|---|---|---|
| Base sintética | Python, exportação em Excel (`.xlsx`) e JSON | A fazer |
| Dados | Snowflake, arquitetura medalhão (Bronze, Prata, Ouro) | A fazer |
| Machine learning | Python (biblioteca a definir), métricas e explicabilidade | A fazer |
| Gestão de modelos | MLflow ou DagsHub (experimentos, métricas e versões) | A fazer |
| Backend | API REST (framework a definir) integrada a Snowflake, MLflow e IA generativa | A fazer |
| IA generativa | Gemini ou ChatGPT | A fazer |
| Frontend | React 19, TypeScript, Vite, React Router, Recharts | ✅ Em andamento |


<h2 align="center" id="arquitetura">🏰 Arquitetura do Repositório <br>
<img src="https://img.shields.io/badge/Architecture-111827?style=flat-square&logo=instructure&logoColor=white" height="22"/>
</h2>

### Visão geral da solução

```mermaid
flowchart LR
  FP[Fontes públicas<br/>ANAC, RI Azul,<br/>Azul Fidelidade, avaliações]

  subgraph E1[1. Base sintética]
    G[Gerador em Python] --> XL[(Excel)]
    G --> JS[(JSON)]
  end

  subgraph E2[2. Snowflake: arquitetura medalhão]
    BR[Bronze<br/>dados brutos] --> PR[Prata<br/>limpos e padronizados] --> OU[Ouro<br/>features e visões analíticas]
  end

  subgraph E34[3 e 4. Machine learning]
    TR[Treino e avaliação<br/>meta: acurácia de 90% ou mais] --> MF[(MLflow / DagsHub<br/>experimentos e versões)]
  end

  subgraph E5[5. Backend]
    API[API REST]
    LLM[IA generativa<br/>Gemini ou ChatGPT]
  end

  subgraph E6[6. Frontend]
    UI[React + TypeScript<br/>Login, Menu, Dashboard, Cliente]
  end

  FP --> G
  XL --> BR
  JS --> BR
  OU --> TR
  OU <--> API
  MF --> API
  API <--> LLM
  UI <--> API
```

### Fluxo completo (etapa 7: integração)

```mermaid
sequenceDiagram
  actor AN as Analista de CRM (Azul)
  participant UI as Frontend
  participant API as Backend
  participant SF as Snowflake
  participant ML as Modelo (MLflow)
  participant IA as IA generativa

  AN->>UI: Entra com e-mail e senha
  UI->>API: POST /auth/login
  API-->>UI: Token de sessão
  AN->>UI: Envia uma base (Excel, CSV ou JSON)
  UI->>API: POST /ingestao/clientes
  API->>SF: Grava na camada Bronze
  SF->>SF: Pipeline Bronze → Prata → Ouro
  AN->>UI: Abre o dashboard ou um cliente
  UI->>API: GET /dashboard/resumo e GET /clientes/{id}
  API->>SF: Consulta a camada Ouro
  API->>ML: Previsão de risco de evasão e CLV
  AN->>UI: Pede uma recomendação
  UI->>API: POST /clientes/{id}/recomendacao
  API->>IA: Perfil, previsão e regras do Azul Fidelidade
  IA-->>API: Ação recomendada e mensagem redigida
  API-->>UI: Recomendação com justificativa
  UI-->>AN: Analista revisa, ajusta e aprova
```

### Ordem de desenvolvimento

Sequência definida na mentoria, priorizando primeiro o que resolve o problema da Azul. As pastas ficam dentro de `MVP-Hackathon-Business-Avanade-Azul/`.

| # | Etapa | Entregável | Pasta | Status |
|---|---|---|---|---|
| 1 | Base sintética | Clientes fictícios em pelo menos dois formatos (Excel e JSON) | `DADOS/` | A fazer |
| 2 | Pipeline no Snowflake | Camadas Bronze, Prata e Ouro, tratadas e documentadas | `SNOWFLAKE/` | A fazer |
| 3 | Modelo de ML | Treino e avaliação sobre a camada Ouro, com acurácia de 90% ou mais | `MODELO/` | A fazer |
| 4 | Gestão do modelo | Experimentos, métricas e versões no MLflow ou DagsHub | `MODELO/` | A fazer |
| 5 | Backend com IA | API que recebe dados do front, consulta o Snowflake, usa o modelo do MLflow e gera recomendações com IA generativa | `BACKEND/` | A fazer |
| 6 | Frontend | Dashboard e tela do cliente, com análises e recomendações da IA | `FRONTEND/` | ✅ Em andamento |
| 7 | Integração e testes | Fluxo completo validado, do envio de dados até a recomendação | todas | A fazer |

> O frontend foi adiantado com uma base sintética local que segue o mesmo contrato da API. Quando o backend existir, basta configurar `VITE_API_URL`; nenhuma tela muda.

### Estrutura de pastas

<pre>
MVP-Hackathon-Business-Avanade-Azul✈️/
├── MVP-Hackathon-Business-Avanade-Azul <img src="https://img.shields.io/badge/-C%C3%B3digo_da_solu%C3%A7%C3%A3o-111827?style=flat-square&logo=github&logoColor=white" height="18"/>/
│   ├── DADOS <img src="https://img.shields.io/badge/-Python-111827?style=flat&logo=python&logoColor=3776AB" height="18"/> <img src="https://img.shields.io/badge/-Base_sint%C3%A9tica_%C2%B7_Excel_e_JSON-111827?style=flat-square&logo=microsoftexcel&logoColor=217346" height="18"/> <img src="https://img.shields.io/badge/-Etapa_1-111827?style=flat-square" height="18"/> <img src="https://img.shields.io/badge/-A_criar-6B7280?style=flat-square" height="18"/>/
│   ├── SNOWFLAKE <img src="https://img.shields.io/badge/-Snowflake-111827?style=flat&logo=snowflake&logoColor=29B5E8" height="18"/> <img src="https://img.shields.io/badge/-Bronze_%C2%B7_Prata_%C2%B7_Ouro-111827?style=flat-square&logo=snowflake&logoColor=29B5E8" height="18"/> <img src="https://img.shields.io/badge/-Etapa_2-111827?style=flat-square" height="18"/> <img src="https://img.shields.io/badge/-A_criar-6B7280?style=flat-square" height="18"/>/
│   ├── MODELO <img src="https://img.shields.io/badge/-Python-111827?style=flat&logo=python&logoColor=3776AB" height="18"/> <img src="https://img.shields.io/badge/-Treino_%C2%B7_avalia%C3%A7%C3%A3o_%C2%B7_MLflow_ou_DagsHub-111827?style=flat-square&logo=mlflow&logoColor=0194E2" height="18"/> <img src="https://img.shields.io/badge/-Etapas_3_e_4-111827?style=flat-square" height="18"/> <img src="https://img.shields.io/badge/-A_criar-6B7280?style=flat-square" height="18"/>/
│   ├── BACKEND <img src="https://img.shields.io/badge/-API_REST_%C2%B7_Snowflake_%C2%B7_modelo_%C2%B7_IA_generativa-111827?style=flat-square&logo=googlegemini&logoColor=8E75B2" height="18"/> <img src="https://img.shields.io/badge/-Etapa_5-111827?style=flat-square" height="18"/> <img src="https://img.shields.io/badge/-Vazia-6B7280?style=flat-square" height="18"/>/
│   └── FRONTEND <img src="https://img.shields.io/badge/-React_19-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/> <img src="https://img.shields.io/badge/-TypeScript-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/> <img src="https://img.shields.io/badge/-Vite-111827?style=flat&logo=vite&logoColor=646CFF" height="18"/> <img src="https://img.shields.io/badge/-React_Router-111827?style=flat&logo=reactrouter&logoColor=CA4245" height="18"/> <img src="https://img.shields.io/badge/-Recharts-111827?style=flat" height="18"/> <img src="https://img.shields.io/badge/-Etapa_6-111827?style=flat-square" height="18"/>/
│       ├── .env.example <img src="https://img.shields.io/badge/-VITE__API__URL_%C2%B7_vazio_usa_a_base_sint%C3%A9tica-111827?style=flat&logo=dotenv&logoColor=ECD53F" height="18"/>
│       ├── .gitignore <img src="https://img.shields.io/badge/-GitIgnore-111827?style=flat&logo=git&logoColor=F05032" height="18"/>
│       ├── .oxlintrc.json <img src="https://img.shields.io/badge/-oxlint_%C2%B7_regras_de_React_e_TS-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│       ├── README.md <img src="https://img.shields.io/badge/-Telas_%C2%B7_dados_%C2%B7_como_rodar-111827?style=flat&logo=markdown&logoColor=white" height="18"/>
│       ├── index.html <img src="https://img.shields.io/badge/-HTML5-111827?style=flat&logo=html5&logoColor=E34F26" height="18"/>
│       ├── package.json <img src="https://img.shields.io/badge/-npm_%C2%B7_dev_%C2%B7_build_%C2%B7_lint_%C2%B7_preview-111827?style=flat&logo=npm&logoColor=CB3837" height="18"/>
│       ├── package-lock.json <img src="https://img.shields.io/badge/-npm_lock-111827?style=flat&logo=npm&logoColor=CB3837" height="18"/>
│       ├── tsconfig.json <img src="https://img.shields.io/badge/-TS_Config-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│       ├── tsconfig.app.json <img src="https://img.shields.io/badge/-TS_Config_(app)-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│       ├── tsconfig.node.json <img src="https://img.shields.io/badge/-TS_Config_(Node)-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│       ├── vite.config.ts <img src="https://img.shields.io/badge/-Vite_Config-111827?style=flat&logo=vite&logoColor=646CFF" height="18"/>
│       ├── public <img src="https://img.shields.io/badge/-Arquivos_est%C3%A1ticos-111827?style=flat-square&logo=vite&logoColor=646CFF" height="18"/>/
│       │   └── favicon.svg <img src="https://img.shields.io/badge/-Favicon-111827?style=flat&logo=svg&logoColor=FFB13B" height="18"/>
│       └── src <img src="https://img.shields.io/badge/-TSX_%C2%B7_TS-111827?style=flat-square&logo=typescript&logoColor=3178C6" height="18"/>/
│           ├── principal.tsx <img src="https://img.shields.io/badge/-Entry_Point-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           ├── Aplicacao.tsx <img src="https://img.shields.io/badge/-Rotas_%C2%B7_login_%C2%B7_menu_%C2%B7_dashboard_%C2%B7_cliente-111827?style=flat&logo=reactrouter&logoColor=CA4245" height="18"/>
│           ├── paginas <img src="https://img.shields.io/badge/-Telas-111827?style=flat-square&logo=react&logoColor=61DAFB" height="18"/>/
│           │   ├── PaginaLogin.tsx <img src="https://img.shields.io/badge/-Login_%C2%B7_e--mail_e_senha-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/> <img src="https://img.shields.io/badge/-Implementada-22C55E?style=flat-square" height="18"/>
│           │   ├── PaginaLogin.css <img src="https://img.shields.io/badge/-CSS-111827?style=flat&logo=css&logoColor=663399" height="18"/>
│           │   ├── PaginaMenu.tsx <img src="https://img.shields.io/badge/-Menu_%C2%B7_busca_%C2%B7_m%C3%B3dulos_%C2%B7_envio_de_base-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/> <img src="https://img.shields.io/badge/-Implementada-22C55E?style=flat-square" height="18"/>
│           │   ├── PaginaMenu.css <img src="https://img.shields.io/badge/-CSS-111827?style=flat&logo=css&logoColor=663399" height="18"/>
│           │   ├── PaginaDashboard.tsx <img src="https://img.shields.io/badge/-Dashboard_%C2%B7_filtros_%C2%B7_matriz_valor_%C3%97_risco-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/> <img src="https://img.shields.io/badge/-Implementada-22C55E?style=flat-square" height="18"/>
│           │   └── PaginaCliente.tsx <img src="https://img.shields.io/badge/-Cliente_%C2%B7_perfil_%C2%B7_risco_%C2%B7_recomenda%C3%A7%C3%A3o_da_IA-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/> <img src="https://img.shields.io/badge/-Implementada-22C55E?style=flat-square" height="18"/>
│           ├── componentes <img src="https://img.shields.io/badge/-Componentes-111827?style=flat-square&logo=react&logoColor=61DAFB" height="18"/>/
│           │   ├── cliente <img src="https://img.shields.io/badge/-Cliente-111827?style=flat-square&logo=react&logoColor=22C55E" height="18"/>/
│           │   │   └── CartaoRecomendacaoIA.tsx <img src="https://img.shields.io/badge/-Pr%C3%B3xima_melhor_a%C3%A7%C3%A3o_%C2%B7_aprova%C3%A7%C3%A3o_humana-111827?style=flat&logo=react&logoColor=22C55E" height="18"/>
│           │   ├── dashboard <img src="https://img.shields.io/badge/-Dashboard-111827?style=flat-square&logo=react&logoColor=F59E0B" height="18"/>/
│           │   │   ├── SegmentosPersona.tsx <img src="https://img.shields.io/badge/-CLV_e_risco_por_persona-111827?style=flat&logo=react&logoColor=F59E0B" height="18"/>
│           │   │   └── TabelaPrioritarios.tsx <img src="https://img.shields.io/badge/-Fila_por_perda_esperada-111827?style=flat&logo=react&logoColor=F59E0B" height="18"/>
│           │   ├── estrutura <img src="https://img.shields.io/badge/-Layout-111827?style=flat-square&logo=react&logoColor=61DAFB" height="18"/>/
│           │   │   ├── LayoutPrincipal.tsx <img src="https://img.shields.io/badge/-Layout-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   │   ├── RotaProtegida.tsx <img src="https://img.shields.io/badge/-Guarda_de_rota-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   │   ├── BuscaCliente.tsx <img src="https://img.shields.io/badge/-Busca_por_nome_ou_ID-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   │   └── MenuUsuario.tsx <img src="https://img.shields.io/badge/-Usu%C3%A1rio_logado_%C2%B7_sair-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   ├── graficos <img src="https://img.shields.io/badge/-Gr%C3%A1ficos_%C2%B7_Recharts-111827?style=flat-square&logo=react&logoColor=E0234E" height="18"/>/
│           │   │   ├── MatrizValorRisco.tsx <img src="https://img.shields.io/badge/-Dispers%C3%A3o_valor_%C3%97_risco-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── Explicabilidade.tsx <img src="https://img.shields.io/badge/-Contribui%C3%A7%C3%B5es_no_estilo_SHAP-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── GraficoReceitaMensal.tsx <img src="https://img.shields.io/badge/-Receita_mensal-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── GraficoVoosMensais.tsx <img src="https://img.shields.io/badge/-Voos_por_m%C3%AAs-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── ComposicaoCategorias.tsx <img src="https://img.shields.io/badge/-Barra_100%25_por_categoria-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── BarrasRanking.tsx <img src="https://img.shields.io/badge/-Barras_horizontais-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   ├── CartaoGrafico.tsx <img src="https://img.shields.io/badge/-Cart%C3%A3o_do_gr%C3%A1fico_%2B_tabela_de_dados-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   │   └── Legenda.tsx <img src="https://img.shields.io/badge/-Legenda-111827?style=flat&logo=react&logoColor=E0234E" height="18"/>
│           │   ├── ingestao <img src="https://img.shields.io/badge/-Ingest%C3%A3o-111827?style=flat-square&logo=snowflake&logoColor=29B5E8" height="18"/>/
│           │   │   └── EnvioBaseClientes.tsx <img src="https://img.shields.io/badge/-Excel_%C2%B7_CSV_%C2%B7_JSON_para_a_camada_Bronze-111827?style=flat&logo=snowflake&logoColor=29B5E8" height="18"/>
│           │   ├── modelo <img src="https://img.shields.io/badge/-Modelo-111827?style=flat-square&logo=mlflow&logoColor=0194E2" height="18"/>/
│           │   │   └── AvisoModelo.tsx <img src="https://img.shields.io/badge/-Vers%C3%A3o_%C2%B7_acur%C3%A1cia_%C2%B7_AUC-111827?style=flat&logo=mlflow&logoColor=0194E2" height="18"/>
│           │   └── ui <img src="https://img.shields.io/badge/-UI_Kit-111827?style=flat-square&logo=react&logoColor=A855F7" height="18"/>/
│           │       ├── Cartao.tsx <img src="https://img.shields.io/badge/-Card-111827?style=flat&logo=react&logoColor=A855F7" height="18"/>
│           │       ├── Indicador.tsx <img src="https://img.shields.io/badge/-KPI-111827?style=flat&logo=react&logoColor=A855F7" height="18"/>
│           │       ├── Medidor.tsx <img src="https://img.shields.io/badge/-Medidor-111827?style=flat&logo=react&logoColor=A855F7" height="18"/>
│           │       ├── Selos.tsx <img src="https://img.shields.io/badge/-Categoria_%C2%B7_persona_%C2%B7_risco_%C2%B7_sentimento-111827?style=flat&logo=react&logoColor=A855F7" height="18"/>
│           │       ├── Icone.tsx <img src="https://img.shields.io/badge/-%C3%8Dcones_SVG-111827?style=flat&logo=react&logoColor=A855F7" height="18"/>
│           │       └── cores.ts <img src="https://img.shields.io/badge/-Cores_de_categoria_e_risco-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── servicos <img src="https://img.shields.io/badge/-Integra%C3%A7%C3%A3o_com_a_API-111827?style=flat-square&logo=typescript&logoColor=3178C6" height="18"/>/
│           │   ├── fonteDeDados.ts <img src="https://img.shields.io/badge/-Contrato_FonteDeDadosCrm-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   ├── servicoCrm.ts <img src="https://img.shields.io/badge/-Escolhe_base_sint%C3%A9tica_ou_API-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   ├── fonteSintetica.ts <img src="https://img.shields.io/badge/-Base_sint%C3%A9tica_local-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   ├── fonteApi.ts <img src="https://img.shields.io/badge/-Fetch_%C2%B7_Bearer_%C2%B7_401_volta_ao_login-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   ├── configuracaoApi.ts <img src="https://img.shields.io/badge/-L%C3%AA_VITE__API__URL-111827?style=flat&logo=vite&logoColor=646CFF" height="18"/>
│           │   ├── servicoAutenticacao.ts <img src="https://img.shields.io/badge/-POST_%2Fauth%2Flogin_%C2%B7_acessos_de_demonstra%C3%A7%C3%A3o-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   └── sessao.ts <img src="https://img.shields.io/badge/-Sess%C3%A3o_no_sessionStorage-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── contextos <img src="https://img.shields.io/badge/-Context_API-111827?style=flat-square&logo=react&logoColor=61DAFB" height="18"/>/
│           │   ├── ProvedorAutenticacao.tsx <img src="https://img.shields.io/badge/-Auth_Provider-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   └── contextoAutenticacao.ts <img src="https://img.shields.io/badge/-Contexto_de_autentica%C3%A7%C3%A3o-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           ├── hooks <img src="https://img.shields.io/badge/-Hooks-111827?style=flat-square&logo=react&logoColor=61DAFB" height="18"/>/
│           │   ├── useAutenticacao.ts <img src="https://img.shields.io/badge/-Usu%C3%A1rio_logado-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           │   └── useBuscaAssincrona.ts <img src="https://img.shields.io/badge/-Busca_sem_piscar_a_tela-111827?style=flat&logo=react&logoColor=61DAFB" height="18"/>
│           ├── tipos <img src="https://img.shields.io/badge/-TypeScript-111827?style=flat-square&logo=typescript&logoColor=3178C6" height="18"/>/
│           │   ├── crm.ts <img src="https://img.shields.io/badge/-Espelha_a_camada_Ouro-111827?style=flat&logo=snowflake&logoColor=29B5E8" height="18"/>
│           │   └── autenticacao.ts <img src="https://img.shields.io/badge/-Usu%C3%A1rio_%C2%B7_sess%C3%A3o-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── dados <img src="https://img.shields.io/badge/-Mock_Data-111827?style=flat-square&logo=json&logoColor=yellow" height="18"/>/
│           │   └── sinteticos <img src="https://img.shields.io/badge/-Base_sint%C3%A9tica-111827?style=flat-square&logo=json&logoColor=yellow" height="18"/>/
│           │       └── gerarClientes.ts <img src="https://img.shields.io/badge/-160_clientes_determin%C3%ADsticos-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── configuracao <img src="https://img.shields.io/badge/-Regras_de_neg%C3%B3cio-111827?style=flat-square&logo=typescript&logoColor=3178C6" height="18"/>/
│           │   ├── personas.ts <img src="https://img.shields.io/badge/-Personas_comportamentais-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   ├── fidelidade.ts <img src="https://img.shields.io/badge/-Categorias_do_Azul_Fidelidade-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           │   └── aeroportos.ts <img src="https://img.shields.io/badge/-C%C3%B3digo_IATA_para_cidade-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── utilitarios <img src="https://img.shields.io/badge/-Utilit%C3%A1rios-111827?style=flat-square&logo=typescript&logoColor=3178C6" height="18"/>/
│           │   └── formatacao.ts <img src="https://img.shields.io/badge/-Formata%C3%A7%C3%A3o_pt--BR-111827?style=flat&logo=typescript&logoColor=3178C6" height="18"/>
│           ├── estilos <img src="https://img.shields.io/badge/-CSS-111827?style=flat-square&logo=css&logoColor=663399" height="18"/>/
│           │   └── global.css <img src="https://img.shields.io/badge/-Tokens_de_cor_%C2%B7_tema_claro_e_escuro-111827?style=flat&logo=css&logoColor=663399" height="18"/>
│           └── imagens <img src="https://img.shields.io/badge/-Assets-111827?style=flat-square" height="18"/>/
│               └── logo-azul.jpg <img src="https://img.shields.io/badge/-Logo-111827?style=flat" height="18"/>
│
├── img <img src="https://img.shields.io/badge/-Assets-111827?style=flat-square" height="18"/>/
│   └── Azul logo.jpg <img src="https://img.shields.io/badge/-Logo_do_README-111827?style=flat" height="18"/>
├── pdf <img src="https://img.shields.io/badge/-PDF-111827?style=flat-square&logo=adobeacrobatreader&logoColor=EC1C24" height="18"/>/
│   └── Desafio_3_Azul_CrmAltoValor.pdf <img src="https://img.shields.io/badge/-Enunciado_do_desafio_%C2%B7_confidencial-111827?style=flat&logo=adobeacrobatreader&logoColor=EC1C24" height="18"/>
├── .gitignore <img src="https://img.shields.io/badge/-GitIgnore-111827?style=flat&logo=git&logoColor=F05032" height="18"/>
└── README.md <img src="https://img.shields.io/badge/-Markdown-111827?style=flat&logo=markdown&logoColor=white" height="18"/>
</pre>

### Contrato entre frontend e backend

O frontend consome apenas estes endpoints. Os formatos de resposta estão em [`FRONTEND/src/tipos/crm.ts`](MVP-Hackathon-Business-Avanade-Azul/FRONTEND/src/tipos/crm.ts) e o cliente HTTP em [`FRONTEND/src/servicos/fonteApi.ts`](MVP-Hackathon-Business-Avanade-Azul/FRONTEND/src/servicos/fonteApi.ts).

| Método | Rota | Uso no frontend | Origem dos dados |
|---|---|---|---|
| `POST` | `/auth/login` | Tela de login; o token vai em `Authorization: Bearer` nas demais chamadas | Cadastro de usuários internos |
| `GET` | `/dashboard/resumo?persona=&tier=` | Indicadores, matriz valor × risco, personas, categorias, atritos | Visões da camada Ouro |
| `GET` | `/clientes?persona=&tier=` | Busca e fila de prioridade | Camada Ouro + previsões |
| `GET` | `/clientes/{id}` | Tela do cliente (perfil, histórico, explicabilidade) | Camada Ouro + modelo |
| `POST` | `/clientes/{id}/recomendacao` | Botão "Gerar nova recomendação" | Modelo + IA generativa |
| `POST` | `/ingestao/clientes` | Envio de base (multipart, campo `arquivo`) | Grava na camada Bronze |
| `GET` | `/modelo` | Aviso de transparência (versão, acurácia, AUC) | MLflow / DagsHub |

### Premissas e IA responsável

- **Dados 100% sintéticos.** Nenhum dado real de cliente é usado; a tela exibe esse aviso o tempo todo.
- **CLV** é a receita projetada em 24 meses caso o cliente seja retido. **Perda esperada = CLV × risco de evasão**, que ordena a fila de prioridade.
- **Explicabilidade:** score de valor e risco são mostrados como soma de contribuições por fator (no estilo SHAP), para o analista entender cada previsão.
- **Segmentação sem vieses:** personas definidas só por comportamento de voo e relacionamento, sem gênero, idade, renda ou outros atributos sensíveis.
- **Humano no controle:** só usuários internos autenticados acessam a ferramenta; a IA sugere, o analista revisa e aprova, e a aprovação registra quem aprovou. Clientes sem consentimento de marketing têm o envio promocional bloqueado (LGPD).
- **Regras do Azul Fidelidade** (categorias, pontos qualificáveis) usadas como premissas ilustrativas; validar com o regulamento vigente antes de uso real.

### Como rodar o frontend

Pré-requisito: [Node.js](https://nodejs.org) 20.19+ ou 22.12+ (já inclui o `npm`). Para conferir: `node -v`.

```bash
cd MVP-Hackathon-Business-Avanade-Azul/FRONTEND
npm install        # só na primeira vez
npm run dev        # abre em http://localhost:5173
```

Abra http://localhost:5173 no navegador e entre com um dos acessos de demonstração:

| Perfil | E-mail | Senha |
|---|---|---|
| Analista | `analista@exemplo.com` | `azul2026` |
| Gestor | `gestor@exemplo.com` | `azul2026` |

> Esses acessos são **exemplos** e só funcionam no modo de demonstração (sem backend), usando a base sintética. Com o backend configurado em `VITE_API_URL` (arquivo `.env`, ver `.env.example`), o login passa a ser validado pela API em `POST /auth/login`.

Outros comandos, executados dentro de `FRONTEND/`:

| Comando | O que faz |
|---|---|
| `npm run build` | Checa os tipos e gera a versão de produção em `dist/` |
| `npm run preview` | Serve a versão de produção localmente |
| `npm run lint` | Verifica o código com o oxlint |

Mais detalhes em [`FRONTEND/README.md`](MVP-Hackathon-Business-Avanade-Azul/FRONTEND/README.md).
