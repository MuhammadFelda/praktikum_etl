"""Konfigurasi koneksi & path. Nilai dibaca dari file .env (jika ada) lalu environment variable."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


_load_dotenv(BASE_DIR / ".env")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

SOURCE_DB = os.getenv("SOURCE_DB", "bank_oltp")   # sumber 1: PostgreSQL
DW_DB = os.getenv("DW_DB", "bank_dw")             # target data warehouse

CSV_SOURCE_DIR = BASE_DIR / os.getenv("CSV_SOURCE_DIR", "data/csv_source")    # sumber 2: CSV
SEED_DIR = BASE_DIR / "data" / "postgres_seed"
SQL_DIR = BASE_DIR / "sql"
LOG_DIR = BASE_DIR / "logs"


def db_url(db: str) -> str:
    """URL koneksi SQLAlchemy (driver psycopg2)."""
    return f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{db}"
