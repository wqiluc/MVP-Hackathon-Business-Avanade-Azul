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

### Responsabilidades por camada

- **Ingestão:** `file_reader.py` suporta CSV, XLS/XLSX e JSON e verifica as
  colunas obrigatórias; a validação do contrato canônico e dos valores de
  upload está no serviço de backend.
- **Bronze:** `duckdb_writer.py` materializa/substitui `bronze.raw_clients`
  usando a conexão DuckDB fornecida pelo orquestrador. Não é append-only.
- **Silver:** `duckdb_transformer.py` projeta e tipa campos, preserva o
  identificador opaco em `client_identifier` e filtra IDs ausentes; não faz
  limpeza genérica de nulos.
- **Gold:** `duckdb_transformer.py` materializa features analíticas, incluindo
  `avg_ticket` e `high_risk_flag`. O `churn_score` é persistido depois do
  scoring pelo adapter correspondente.

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

## Candidato, publicação e recuperação

O upload percorre leitura e validação do arquivo, staging/candidate, geração de
Bronze, Silver e Gold, scoring, validação do resultado e publicação. A API só
deve considerar concluída a ingestão depois da publicação e da resposta de
contagem do snapshot.

- **DuckDB:** staging e transformações ocorrem em uma transação. A publicação
  das camadas e do registro `gold.snapshot_publication` é confirmada por um
  único commit. Leitores veem o snapshot anterior até o commit; falha antes do
  commit faz rollback. Um lock não bloqueante por caminho de banco rejeita
  uploads concorrentes no mesmo processo. Esse lock não coordena processos
  distintos.
- **Snowflake:** candidatos são tabelas temporárias/sessão-local; schema,
  staging e scoring acontecem antes da transação de publicação. Uma linha de
  controle singleton serializa escritores. Depois do lock, apenas `DELETE` /
  `INSERT` e leituras das tabelas ativas ocorrem entre `BEGIN` e `COMMIT`, pois
  DDL pode causar commit implícito. Erros antes da publicação descartam os
  candidatos; erros durante a publicação executam rollback. O último commit
  bem-sucedido vence, não necessariamente o upload iniciado por último.
- **Ambiguidade de rede:** se a conexão cair durante `COMMIT`, não se deve
  presumir que o rollback ocorreu. Após restabelecer conexão, confira
  `gold.snapshot_publication` ou o ID ativo equivalente. O resultado deve ser
  o snapshot antigo completo ou o novo completo; não existe histórico de
  snapshots nem restauração pelo produto.

Cada requisição de leitura observa um estado confirmado, mas requisições
separadas podem ficar em lados diferentes de uma publicação. Não há pinning de
snapshot entre chamadas, backup histórico ou cancelamento de upload. As
garantias Snowflake de lock, isolamento, permissões e comportamento de rede
requerem validação opt-in em uma conta de teste dedicada; os testes locais
mockados não as comprovam.
