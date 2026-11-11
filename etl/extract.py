import logging
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from config import CHUNKSISE, CSV_DIR, CSV_FILES, SQL_TABLES

log = logging.getLogger(__name__)

def extract_sql(src_engine: Engine) -> dict[str, pd.DataFrame]:
    data = {}
    with src_engine.connect() as conn:
        for table in SQL_TABLES:
            df = pd.read_sql(text(f'SELECT * FROM "{table}"'), conn)
            log.info("Extract SQL %-8s: %7d rows", table, len(df))
            data[table] = df
    return data

def extract_csv() -> dict[str, pd.DataFrame]:
    data = {}
    for name, filename in CSV_FILES.items():
        df = pd.read_csv(CSV_DIR / filename)
        log.info("Extract CSV %-8s: %7d", name, len(df))
        data[name] = df
    return data

def save_to_staging(data: dict[str, pd.DataFrame], dw_engine: Engine):
    with dw_engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        for name, df in data.items():
                df.to_sql(
                    f"stg_{name}", conn, schema="staging",
                    if_exists="replace", index=False,
                    chunksize=CHUNKSISE, method="multi"
                )
                log.info("Staging stg_%-8s: %7d rows", name, len(df))

def extract_all(src_engine: Engine, dw_engine: Engine) -> dict[str, pd.DataFrame]:
    data = {**extract_sql(src_engine), **extract_csv()}
    save_to_staging(data, dw_engine)
    return data