import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

SEED_TABLES = ["client", "account", "disp", "loan", "trans"]

def autocommit_engine(db: str):
    # AUTOCOMMIT: CREATE DATABASE tidak boleh di dalam transaksi, dan file seed punya BEGIN/COMMIT sendiri
    return create_engine(config.db_url(db), isolation_level="AUTOCOMMIT")


def create_database_if_missing(name: str) -> None:
    engine = autocommit_engine("postgres")
    with engine.connect() as conn:
        ada = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar()
        if ada:
            print(f"[=] database {name} sudah ada")
        else:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            print(f"[+] database {name} dibuat")
    engine.dispose()


def run_sql_file(db: str, path: Path) -> None:
    engine = autocommit_engine(db)
    with engine.connect() as conn:
        conn.exec_driver_sql(path.read_text(encoding="utf-8"))  # menjalankan banyak statement sekaligus
    engine.dispose()


def seed_source() -> None:
    for i, table in enumerate(SEED_TABLES, 1):
        path = config.SEED_DIR / f"{i:02d}_{table}.sql"
        run_sql_file(config.SOURCE_DB, path)
        engine = create_engine(config.db_url(config.SOURCE_DB))
        with engine.connect() as conn:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        engine.dispose()
        print(f"    {path.name:<15} -> {table:<8} {n:>7} baris")


if __name__ == "__main__":
    create_database_if_missing(config.SOURCE_DB)
    create_database_if_missing(config.DW_DB)
    run_sql_file(config.SOURCE_DB, config.SQL_DIR / "01_source_oltp.sql")
    print(f"[+] 01_source_oltp.sql dijalankan di {config.SOURCE_DB}")
    seed_source()
    run_sql_file(config.DW_DB, config.SQL_DIR / "02_dw_star_schema.sql")
    print(f"[+] 02_dw_star_schema.sql dijalankan di {config.DW_DB}")
    print("Selesai. Sekarang jalankan: python etl.py")
