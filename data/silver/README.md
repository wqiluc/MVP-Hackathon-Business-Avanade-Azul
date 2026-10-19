# Silver layer

`duckdb_transformer.py` projeta os campos Silver, converte tipos, remove linhas
sem `id_cliente` e preserva em `client_identifier` o identificador opaco HMAC
preparado por `DataLakeService` antes da persistência na Bronze. Não executa
limpeza genérica de nulos.
