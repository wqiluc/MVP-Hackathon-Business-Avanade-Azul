# Data Lake — base de clientes expandida (Bronze → Silver → Gold)

Fluxo construído sobre a base `clientes_sinteticos_snowflake_10000.csv`, que
substitui a antiga base de 2000 clientes. Os 2000 clientes originais
(`CLI-100000` a `CLI-101999`) estão nela sem alteração; os outros 8000
(`CLI-102000` a `CLI-109999`) foram gerados por amostragem dos padrões dos
originais (tier, estado, risco, pontos, voos). O pipeline enriquece essa base
com colunas de comportamento de viagem, fidelidade e experiência. Para crescer
além de 10.000, `gerar --total N` expande pelo mesmo bootstrap.

```
clientes_sinteticos_snowflake_10000.csv  (base, 9 colunas)
        │  python pipeline_datalake.py gerar
        ▼
bronze/clientes_azul_bronze.csv          → AZUL_DATA_LAKE.BRONZE.CLIENTES_AZUL_RAW
        │  python pipeline_datalake.py tratar
        ▼
silver/clientes_azul_silver.csv          → AZUL_DATA_LAKE.SILVER.CLIENTES_AZUL
silver/relatorio_qualidade_silver.json
        ▼
gold/clientes_azul_gold.csv              → AZUL_DATA_LAKE.GOLD.CLIENTES_AZUL
gold/resumo_gold.json                       AZUL_DATA_LAKE.GOLD.VW_CONTEXTO_IA (sem PII)
        │  python pipeline_datalake.py enviar   (sobe as 3 camadas)
        │  python pipeline_datalake.py trazer   (baixa a GOLD do Snowflake para cá)
        ▼
main.py (FastAPI) → front-end  |  /contexto-ia → agente de IA
```

## Como rodar

```bash
pip install -r requirements.txt
python pipeline_datalake.py gerar                 # Bronze (--total N > 10000 expande a base)
python pipeline_datalake.py tratar                # Silver + Gold
python pipeline_datalake.py ddl                   # regrava sql/06_clientes_azul_expandido.sql
python pipeline_datalake.py enviar                # precisa do .env com SNOWFLAKE_*
python pipeline_datalake.py trazer                # GOLD do Snowflake -> gold/clientes_azul_gold.csv
uvicorn main:app --reload                         # API para o front-end
```

A geração é determinística (seed 42, data de referência 2026-10-20).

## Bronze — o que chega, como chegou

Tudo como texto, com as 9 colunas originais, 24 colunas novas e 2 de linhagem
(`ORIGEM_REGISTRO`, `DATA_INGESTAO`). Simula problemas reais de ingestão para a
Silver tratar: snapshots duplicados, categoria com grafias diferentes, UF em
minúsculas, e-mail em maiúsculas ou inválido, decimal com vírgula, NPS fora da
faixa, tarifa vazia e dados pessoais escritos no comentário livre. Ruídos
irreversíveis (e-mail sem `@`) só são aplicados a clientes criados por uma
expansão além da base, nunca aos clientes do CSV.

## Silver — tratamento aplicado

Cada regra e a quantidade de registros afetados ficam em `silver/relatorio_qualidade_silver.json`.

| Regra | Ação |
|---|---|
| Categoria `BASICO`, `Básico `, `topazio`… | padroniza para `Basico`, `Topazio`, `Safira`, `Diamante` |
| UF com espaço/minúscula | `strip` + maiúscula |
| E-mail | minúsculas; `EMAIL_VALIDO` sinaliza formato inválido |
| Mesmo e-mail em clientes diferentes | `EMAIL_DUPLICADO` (já existiam 4 pares na base original) |
| Decimal com vírgula | converte para ponto |
| NPS fora de 0–10 | anula |
| Tarifa vazia | imputa a moda do mesmo `MOTIVO_VIAGEM` |
| Snapshot duplicado do cliente | mantém o `DATA_ATUALIZACAO` mais recente |
| Pontos a expirar > saldo | limita ao saldo |
| CPF, e-mail ou telefone no comentário | mascara (`[CPF]`, `[EMAIL]`, `[TELEFONE]`), por LGPD |
| Comentário livre | `SENTIMENTO_SCORE` (-1 a 1) e `SENTIMENTO_ULTIMO_CONTATO` (léxico PT-BR) |
| Tipos | inteiros, decimais, booleanos e datas tipados (ver DDL) |

## Gold — o que vai para o front-end e para a IA

| Grupo | Colunas | Como é calculado |
|---|---|---|
| Identificação | `CUSTOMER_ID`, `NOME`, `EMAIL`, `ESTADO`, `AEROPORTO_BASE`, `CATEGORIA_TIER`, `MESES_RELACIONAMENTO` | `NOME` e `EMAIL` só para o operador de CRM |
| Valor (RFM + CLV) | `VOOS_ANO`, `VOOS_ANO_ANTERIOR`, `TENDENCIA_VOOS`, `GASTO_TOTAL_12M`, `TICKET_MEDIO`, `DIAS_DESDE_ULTIMO_VOO`, `SCORE_VALOR`, `CLV_ESTIMADO_36M`, `SEGMENTO_VALOR`, `ALTO_VALOR` | Score 0–100 = 35% gasto + 25% frequência + 15% recência + 25% potencial. CLV = receita anual × retenção, 3 anos, desconto de 12% a.a. Alto valor = top 20% de CLV |
| Risco de evasão | `RISCO_CHURN` (origem), `PROB_CHURN_90D`, `FATORES_RISCO` | Scorecard logístico: recência vs. intervalo habitual, queda de voos, atrasos, reclamações, NPS, sentimento; cartão e clube reduzem o risco. `FATORES_RISCO` traz os 3 fatores que mais pesaram |
| Persona | `PERSONA`, `PERSONA_MOTIVO` | Executivo Frequente, Lazer & Família, Caçador de Pontos ou Ocasional, por regra explicável |
| Padrão de viagem | `MOTIVO_VIAGEM`, `ROTA_FAVORITA`, `TARIFA_PREFERIDA`, `USA_ESPACO_AZUL`, `VIAJA_INTERNACIONAL`, `ANTECEDENCIA_MEDIA_DIAS`, `DIA_SEMANA_PREFERIDO`, `ACOMPANHANTES_MEDIA`, `CANAL_COMPRA` | — |
| Próxima viagem | `PROXIMA_VIAGEM_DATA`, `PROXIMA_VIAGEM_JANELA_COMPRA`, `PROXIMA_VIAGEM_ROTA`, `PROXIMA_VIAGEM_TARIFA`, `PROXIMA_VIAGEM_PAGAMENTO`, `PROXIMA_VIAGEM_CONFIANCA` | Último voo + intervalo médio; janela de compra = data − antecedência |
| Fidelidade | `PONTOS_ACUMULADOS`, `PONTOS_A_EXPIRAR_90D`, `RESGATES_PONTOS_12M`, `CARTAO_AZUL_ITAU`, `CLUBE_AZUL`, `CATEGORIA_PROJETADA`, `RISCO_REBAIXAMENTO`, `PROXIMA_CATEGORIA`, `FALTAM_TRECHOS_PROXIMA` | Regras 2026 do Azul Fidelidade (trechos/pontos qualificáveis e atalhos por cartão/clube) |
| Experiência | `ATRASOS_SOFRIDOS_12M`, `RECLAMACOES_12M`, `NPS_ULTIMO`, `SENTIMENTO_ULTIMO_CONTATO`, `COMENTARIO_ULTIMO_CONTATO` | Comentário já mascarado na Silver |
| Ação | `ACAO_RECOMENDADA`, `ACAO_DESCRICAO`, `CANAL_CONTATO`, `PRIORIDADE_CRM`, `DATA_REFERENCIA` | Regras de próxima melhor ação; sem opt-in o canal é `SOMENTE_SERVICO`. Prioridade = ranking de CLV × risco |

Os tipos de cada coluna no Snowflake estão em `sql/06_clientes_azul_expandido.sql`.

### Campos enviados ao agente de IA

Tudo da Gold **exceto** `NOME`, `EMAIL` e `COMENTARIO_ULTIMO_CONTATO` (lista em
`COLUNAS_CONTEXTO_IA`, exposta em `GET /api/customers/{id}/contexto-ia` e na view
`GOLD.VW_CONTEXTO_IA`). O agente recebe números já calculados (valor, risco e seus
fatores, persona, previsão da viagem, ação sugerida) e fica responsável por
explicar e redigir a oferta, apoiado nas regras públicas do Azul Fidelidade.

## Premissas e fontes públicas

| Premissa | Valor | Fonte |
|---|---|---|
| Tarifa média doméstica | R$ 648 | ANAC, Anuário do Transporte Aéreo 2025 |
| Topázio / Safira | 6 / 10 trechos **ou** 6 mil / 10 mil pontos qualificáveis | Regras 2026 divulgadas por passageirodeprimeira.com (validar no site oficial) |
| Diamante | 12 trechos **e** 12 mil pontos, ou R$ 25 mil | idem |
| Atalhos de categoria | Azul Itaú Gold → Topázio; Platinum/Clube 10.000 → Safira; Infinite/Clube 20.000 → Diamante | idem |
| Pontos qualificáveis | R$ 1 = 1 ponto | idem |
| Multiplicadores de tarifa | MaisAzul 1,35×; Business 3×; internacional 1,6× | Premissa do MVP |

Na base gerada, o ticket médio doméstico fica em ~R$ 780 (cerca de 20% acima
da média ANAC), o que é coerente com uma base com mais MaisAzul e compras de
última hora.

## Arquivos legados nesta pasta

`bronze/seed_*.json`, `bronze/stream_*.json`, `silver/silver_clientes_higienizados.json`
e `gold/gold_retencao_azul.*` vêm do fluxo Node anterior (Prisma/Faker) e não são
usados por este pipeline.
