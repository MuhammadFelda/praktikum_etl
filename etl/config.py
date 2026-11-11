import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent
ENV = BASE_DIR / ".env"

if not ENV.exists():
    raise FileNotFoundError(
        ".env file not exist"
    )

load_dotenv(ENV, override=False)

def _env(key: str) -> str:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        found = sorted(k for k in os.environ if k.startswith(("DB_", "DW_")))
        raise KeyError(
            f"Variabel {key} belum diisi di {ENV}. "
            f"Variabel DB_/DW_ yang terbaca: {found or 'tidak ada'}"
        )
    return value.strip()

def _db_url(database: str) -> URL:
    return URL.create(
        drivername="postgresql+psycopg2",
        username=_env("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=_env("DB_HOST"), 
        port=int(_env("DB_PORT")),
        database=database,
    )

DB_NAME = _env("DB_NAME")
DW_NAME = _env("DW_NAME")
DB_URL = _db_url(DB_NAME)
DW_URL = _db_url(DW_NAME)

SQL_TABLES = ["client", "account", "disp", "loan", "trans"]
CSV_DIR = BASE_DIR / "data" / "csv"
CSV_FILES = {
    "district": "district.csv",
    "card": "card.csv",
    "order": "order.csv"
}

CHUNKSISE = 5000
TANGGAL_ACUAN_UMUR = "1999-01-01"