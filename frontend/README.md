# Frontend: CRM de Alto Valor

Interface interna para as equipes de CRM, Fidelidade e Relacionamento da Azul. Construída em **React 19 + TypeScript + Vite**, com **React Router** e **Recharts**.

## Como rodar

```bash
npm install
npm run dev       # servidor de desenvolvimento (http://localhost:5173)
npm run build     # checagem de tipos + build de produção em dist/
npm run lint      # oxlint
npm run preview   # serve o build localmente
```

## Telas

| Rota | Tela | O que mostra |
|---|---|---|
| `/login` | **Login** | E-mail e senha; no modo sintético mostra o acesso de demonstração. Todas as outras rotas exigem login e, depois de entrar, o usuário volta para a página que tinha pedido |
| `/` | **Menu** | Busca de cliente, números da base, módulos, envio de base (Excel/CSV/JSON) e os 3 clientes que pedem ação agora |
| `/dashboard` | **Dashboard** | Filtros (persona, categoria), indicadores, matriz valor × risco, segmentação por persona, receita mensal, composição por categoria, atritos da jornada e fila de prioridade |
| `/clientes/:id` | **Cliente** | Perfil, CLV, score de valor, risco de evasão, recomendação da IA (editável, com aprovação humana), explicabilidade dos dois modelos, voos por mês, rotas favoritas e interações |
| `/clientes` | | Abre o primeiro cliente da fila de prioridade |

Os filtros do dashboard ficam na URL (`?persona=…&categoria=…`), então uma visão filtrada pode ser compartilhada por link.

## Dados: backend ou modo sintético

Todas as telas falam com `servicoCrm` ([src/servicos/servicoCrm.ts](src/servicos/servicoCrm.ts)), que implementa o contrato `FonteDeDadosCrm` ([src/servicos/fonteDeDados.ts](src/servicos/fonteDeDados.ts)):

- **Sem `VITE_API_URL`:** só em desenvolvimento (`npm run dev`) ou com `VITE_ENABLE_DEMO_MODE=true` explícito usa a base sintética local ([src/dados/sinteticos/gerarClientes.ts](src/dados/sinteticos/gerarClientes.ts)), com 160 clientes determinísticos, e o login aceita só os acessos de demonstração:

  | Perfil | E-mail | Senha |
  |---|---|---|
  | Analista | `analista@exemplo.com` | `azul2026` |
  | Gestor | `gestor@exemplo.com` | `azul2026` |

- **Com `VITE_API_URL`:** usa o backend real ([src/servicos/fonteApi.ts](src/servicos/fonteApi.ts)). Erros da API nunca caem para dados sintéticos.
- **Build de produção sem `VITE_API_URL` e sem `VITE_ENABLE_DEMO_MODE=true`:** falha de forma fechada (login e dados retornam erro de configuração). Nunca use chaves de API no frontend.

```bash
cp .env.example .env
# edite VITE_API_URL=http://localhost:8000/api/v1
```

### Endpoints esperados

Depois do login, toda chamada leva `Authorization: Bearer <token>`. Uma resposta `401` encerra a sessão e volta para `/login`.

| Método | Rota | Resposta (`src/tipos/crm.ts`) |
|---|---|---|
| `POST` | `/auth/login` (JSON `{ email, senha }`) | `Sessao` (`src/tipos/autenticacao.ts`); `401` para credenciais inválidas |
| `GET` | `/dashboard/resumo?persona=&tier=` | `ResumoDashboard` |
| `GET` | `/clientes?persona=&tier=` | `ClienteResumo[]` |
| `GET` | `/clientes/{id}` | `Cliente` (404 → "cliente não encontrado") |
| `POST` | `/clientes/{id}/recomendacao` | `ProximaAcao` (com `origem: "ia-generativa"`) |
| `POST` | `/ingestao/clientes` (multipart, campo `arquivo`) | `ReciboIngestao` |
| `GET` | `/modelo` | `ModeloInfo` (versão e métricas do MLflow) |

## Estrutura

```
src/
├── principal.tsx              # ponto de entrada
├── Aplicacao.tsx              # rotas
├── paginas/                   # PaginaLogin, PaginaMenu, PaginaDashboard, PaginaCliente
├── componentes/
│   ├── estrutura/             # LayoutPrincipal (menu lateral), RotaProtegida, MenuUsuario, BuscaCliente
│   ├── dashboard/             # SegmentosPersona, TabelaPrioritarios
│   ├── cliente/               # CartaoRecomendacaoIA
│   ├── graficos/              # MatrizValorRisco, GraficoReceitaMensal, GraficoVoosMensais,
│   │                          # Explicabilidade, ComposicaoCategorias, BarrasRanking, Legenda, CartaoGrafico
│   ├── modelo/                # AvisoModelo (transparência do modelo em uso)
│   ├── ingestao/              # EnvioBaseClientes
│   └── ui/                    # Cartao, Indicador, Medidor, Selos, Icone, cores
├── contextos/                 # ProvedorAutenticacao (usuário logado)
├── servicos/                  # servicoCrm, fonteDeDados (contrato), fonteSintetica, fonteApi,
│                              # servicoAutenticacao, sessao, configuracaoApi
├── tipos/                     # crm.ts (domínio) e autenticacao.ts
├── dados/sinteticos/          # gerador da base sintética local
├── configuracao/              # personas, regras do Azul Fidelidade, aeroportos
├── hooks/                     # useBuscaAssincrona, useAutenticacao
├── utilitarios/formatacao.ts  # moeda, números e datas em pt-BR
├── estilos/global.css         # tokens de cor e componentes
└── imagens/
```

Arquivos com nome fixo pelas ferramentas (`index.html`, `package.json`, `vite.config.ts`, `tsconfig*.json`, `public/`) ficaram com o nome original.

## Decisões de interface

- **Cores dos gráficos validadas** para daltonismo e contraste; rampa ordinal para as categorias do programa; cores de status (baixo, moderado, alto, crítico) sempre com ícone e rótulo.
- **Toda visualização tem versão em tabela** (botão "Gráfico / Tabela") ou valores rotulados.
- **Tema claro e escuro** automáticos, seguindo o sistema operacional.
- **Explicabilidade aditiva:** azul = favorável à Azul, vermelho = desfavorável, em ambos os modelos.
- **Humano no controle:** a recomendação da IA só segue depois de "Aprovar ação", que registra quem aprovou; o envio fica bloqueado para clientes sem consentimento de marketing.
- **Sessão:** guardada no `sessionStorage` (some ao fechar a aba), com expiração; a senha nunca é armazenada.
