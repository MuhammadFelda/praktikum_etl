import logging
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from config import CHUNKSISE

log = logging.getLogger(__name__)
LOAD_ORDER = [
    "dim_waktu", "dim_wilayah", "dim_nasabah", "dim_rekening",
    "dim_jenis_transaksi", "dim_status_pinjaman",
    "fact_transaksi", "fact_pinjaman"
]

def load_dw(tables: dict[str, pd.DataFrame], dw_engine: Engine):
    with dw_engine.begin() as conn:
        all_tables = ", ".join(f"dw.{t}" for t in LOAD_ORDER)
        conn.execute(text(  f"TRUNCATE {all_tables} RESTART IDENTITY CASCADE"))
        for name in LOAD_ORDER:
            tables[name].to_sql(
                name, conn, schema="dw", if_exists="append", index=False,
                chunksize=CHUNKSISE, method="multi",
            )
            log.info("Load dw.%-8s: %7s rows", name, len(tables[name]))

def validate(src: dict[str, pd.DataFrame], dw_engine: Engine):
    checks = [
        ("trans -> fact_transaksi", len(src["trans"]),
         "SELECT COUNT(*) FROM dw.fact_transaksi"),
        ("loan -> fact_pinjaman ", len(src["loan"]),
         "SELECT COUNT(*) FROM dw.fact_pinjaman"),
        ("total amount transaksi ", round(float(pd.to_numeric(src["trans"]["amount"]).sum()), 2),
         "SELECT ROUND(SUM(jumlah)::numeric, 2) FROM dw.fact_transaksi"),
        ("total amount pinjaman  ", round(float(pd.to_numeric(src["loan"]["amount"]).sum()), 2),
         "SELECT ROUND(SUM(jumlah_pinjaman)::numeric, 2) FROM dw.fact_pinjaman"),
    ]

    with dw_engine.connect() as conn:
        for label, expected, sql, in checks:
            actual = float(conn.execute(text(sql)).scalar() or 0)
            status = "OK" if abs(actual - expected) < 0.01 else "TIDAK COCOK"
            log.info("Validasi %s : source=%s dw=%s [%s]", label, expected, actual, status)