import logging
import time
from sqlalchemy import create_engine
from config import DW_URL, DB_URL
from extract import extract_all
from load import load_dw, validate
from transform import transform_all

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)

log = logging.getLogger("etl")

def main():
    start = time.time()
    db_engine = create_engine(DB_URL)
    dw_engine = create_engine(DW_URL)
    log.info("Source: %s", DB_URL)
    log.info("Target: %s", DW_URL)

    log.info("=== Extract ===")
    raw = extract_all(db_engine, dw_engine)

    log.info("=== Transform ===")
    tables = transform_all(raw)

    log.info("=== Load ===")
    load_dw(tables, dw_engine)

    log.info("=== Validate ===")
    validate(raw, dw_engine)

    db_engine.dispose()
    dw_engine.dispose()
    log.info("ETL Process Done in %.1f", time.time() - start)

if __name__ == "__main__":
    main()