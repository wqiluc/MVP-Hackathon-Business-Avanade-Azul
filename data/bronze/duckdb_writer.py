class DuckDBBronzeWriter:
    @staticmethod
    def write_raw_clients(conn, df_raw):
        conn.execute("CREATE OR REPLACE TABLE bronze.raw_clients AS SELECT * FROM df_raw")
