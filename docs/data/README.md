# Data layer atual

`data/` é a camada atual de engenharia de dados.
`backend/app/services/datalake_service.py` coordena o fluxo Bronze → Silver →
Gold e seleciona o backend configurado:

1. `data/ingestion/file_reader.py` lê CSV, XLS/XLSX e JSON e valida as colunas
   obrigatórias.
2. `DataLakeService` substitui `id_cliente` por um identificador opaco HMAC-SHA256
   antes de entregar os dados a qualquer backend. O valor original não é
   persistido; IDs repetidos no conjunto mantêm o mesmo identificador. O HMAC
   usa `JWT_SECRET_KEY` com separação de domínio, por isso o identificador
   permanece estável enquanto essa chave não mudar.
3. No caminho local DuckDB, `data/bronze/duckdb_writer.py` substitui
   `bronze.raw_clients`.
4. `data/silver/duckdb_transformer.py` projeta e tipa os campos Silver,
   preservando o identificador opaco recebido; remove linhas sem `id_cliente`,
   sem limpeza genérica de valores nulos.
5. `data/gold/duckdb_transformer.py` calcula `avg_ticket` e `high_risk_flag`.
6. `data/storage/duckdb_adapter.py` inicializa schemas, lê Gold e substitui
   Gold após o scoring; o chamador abre e fecha a conexão.

`DataLakeService` mantém a ordem Bronze → Silver → Gold → scoring → contagem.
DuckDB é o backend local para desenvolvimento e testes. O backend seleciona
DuckDB ou Snowflake por configuração (`DATA_LAKE_BACKEND`). O adapter
Snowflake está em `backend/app/services/snowflake_service.py`; seu contrato
SQL canônico e as transformações versionadas estão em
[`infrastructure/snowflake/`](../../infrastructure/snowflake/README.md) e
requerem uma conta Snowflake externa configurada.

## Fixture local para upload

O gerador de teste fica fora da UI em
[`scripts/generate_synthetic_clients.py`](../../scripts/generate_synthetic_clients.py).
Ele escreve somente as colunas canônicas `id_cliente`, `tier`, `frequencia`,
`recencia_dias`, `gasto_total` e `incidentes`, aceitas pelo `FileReader`; não
altera nem flexibiliza o contrato de ingestão. Gere um fixture local com:

```bash
backend/.venv/bin/python scripts/generate_synthetic_clients.py \
  --output /tmp/synthetic_clients.csv --rows 20
```

Esse arquivo é para desenvolvimento e testes locais. Não há botão para gerá-lo
na interface de produção.

O diretório legado `dados/` foi removido. Seus SQL antigos, inclusive os que
estavam em `dados/sql/`, são apenas uma referência histórica: não existem mais
no checkout atual e não há dependência funcional deles.

## Contrato Snowflake

Snowflake é o backend de Data Lake destinado ao ambiente de integração; DuckDB
permanece como opção local. O caminho de upload da API delega a
`DataLakeService`, que roteia para o adapter selecionado sem colocar SQL nas
rotas. Os objetos canônicos são
`BRONZE.BRONZE_CLIENTS`,
`SILVER.CLEANED_CLIENTS` e `GOLD.CLIENT_FEATURES`. As colunas e os scripts
versionados de configuração e transformação estão em
[`infrastructure/snowflake/`](../../infrastructure/snowflake/README.md) e
definem o contrato Snowflake usado pelo backend do CRM de Alto Valor.

Os dois backends preservam as mesmas transformações Silver (identificador
opaco HMAC preparado antes da persistência, tier normalizado, casts numéricos
e filtro de ID não nulo) e as regras Gold (ticket médio com proteção para
frequência zero e indicador de risco). Alterar `JWT_SECRET_KEY` também altera
os identificadores derivados; uma rotação dessa chave requer migração
coordenada dos dados e consumidores que dependem desses IDs. O scoring ML
continua após Gold: o `ChurnPredictor` chama MLflow Serving e grava
`churn_score` no backend selecionado. Erros de conexão
Snowflake ou Serving são propagados; não são substituídos silenciosamente por
um score local.

Bronze mantém semântica de substituição: cada upload substitui a entrada atual
e Silver/Gold são reconstruídas a partir desse snapshot; não é um histórico
append-only. A integração Snowflake depende de credenciais, permissões, banco
configurado e MLflow Serving acessível. Testes de contrato SQL, isoladamente,
não comprovam uma conta externa ativa. IDs originais já presentes em snapshots
antigos não são apagados nem migrados por esta mudança; a próxima ingestão
substituirá as tabelas e persistirá somente os identificadores opacos.
