"""
ETL Data Warehouse Perbankan  (tools: SQLAlchemy + pandas)
==========================================================
EXTRACT   Sumber 1 = SQL : database PostgreSQL bank_oltp (diisi dari data/postgres_seed/*.sql)
                           tabel account, client, disp, loan, trans  -> pandas.read_sql
          Sumber 2 = CSV : data/csv_source/district.csv              -> pandas.read_csv
          (order.csv & card.csv tidak dipakai, sesuai logical model)
TRANSFORM pandas: dim_waktu, dim_akun, dim_jenis_transaksi, dim_status_pinjaman,
          fact_transaksi, fact_pinjaman (fact constellation)
LOAD      DataFrame.to_sql lewat SQLAlchemy ke schema dw, full refresh dalam satu transaksi.
          Baris fakta tanpa pasangan dimensi ditulis ke logs/reject_<tabel>_<waktu>.csv

Jalankan  python etl.py
"""
import logging
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import config

config.LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[logging.FileHandler(config.LOG_DIR / "etl.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("etl")

TIDAK_DIKETAHUI = "Tidak diketahui"
NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
# batas kelompok umur pemilik saat akun dibuka (usulan logical model, boleh diubah)
UMUR_BINS = [-1, 24, 34, 44, 54, 200]
UMUR_LABEL = ["<25", "25-34", "35-44", "45-54", "55+"]
TIPE_MASUK = {"PRIJEM"}  # PRIJEM = kredit (uang masuk); VYDAJ & VYBER = uang keluar
# Deskripsi status pinjaman menurut dokumentasi dataset PKDD'99 Financial (Berka).
# Cocokkan lagi dengan dokumentasi dari dosen sebelum laporan final.
STATUS_PINJAMAN = {
    "A": ("Kontrak selesai, tanpa masalah", "Lancar"),
    "B": ("Kontrak selesai, pinjaman belum dibayar", "Bermasalah"),
    "C": ("Kontrak berjalan, pembayaran lancar", "Lancar"),
    "D": ("Kontrak berjalan, nasabah menunggak", "Bermasalah"),
}
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")


# ==========================================================================
# EXTRACT
# ==========================================================================
def extract(src_engine: Engine) -> dict:
    src = {}
    with src_engine.connect() as conn:
        for t in ["account", "client", "disp", "loan", "trans"]:
            src[t] = pd.read_sql(text(f"SELECT * FROM {t}"), conn)
            log.info("EXTRACT  sql.%-9s %7d baris", t, len(src[t]))
    src["district"] = pd.read_csv(config.CSV_SOURCE_DIR / "district.csv")
    log.info("EXTRACT  csv.%-9s %7d baris", "district", len(src["district"]))
    return src


def load_staging(src: dict, dw_engine: Engine) -> None:
    """Salinan mentah tiap sumber ke schema staging (jejak audit)."""
    with dw_engine.begin() as conn:
        for name, df in src.items():
            df.to_sql(f"src_{name}", conn, schema="staging", if_exists="replace",
                      index=False, method="multi", chunksize=5000)
    log.info("STAGING  %d tabel mentah disalin ke schema staging", len(src))


# ==========================================================================
# TRANSFORM - dimensi
# ==========================================================================
def build_dim_waktu(trans: pd.DataFrame, loan: pd.DataFrame) -> pd.DataFrame:
    tanggal = pd.concat([pd.to_datetime(trans["date"]), pd.to_datetime(loan["date"])])
    tgl = pd.date_range(tanggal.min(), tanggal.max(), freq="D")
    return pd.DataFrame({
        "id_waktu": tgl.strftime("%Y%m%d").astype(int),
        "tanggal": tgl.date,
        "hari": [NAMA_HARI[d] for d in tgl.dayofweek],
        "bulan": tgl.month,
        "kuartal": tgl.quarter,
        "tahun": tgl.year,
    })


def build_dim_akun(account, district, disp, client) -> pd.DataFrame:
    a = account.copy()
    a["tgl_buka"] = pd.to_datetime(a["date"])

    d = district.rename(columns={"A2": "nama_distrik", "A3": "region",
                                 "A11": "rata_gaji", "A13": "tingkat_pengangguran"})
    a = a.merge(d[["district_id", "nama_distrik", "region", "rata_gaji", "tingkat_pengangguran"]],
                on="district_id", how="left")

    # pemilik akun = disp bertipe OWNER (jika lebih dari satu, ambil disp_id terkecil)
    owner = (disp[disp["type"] == "OWNER"].sort_values("disp_id")
             .drop_duplicates("account_id")[["account_id", "client_id"]]
             .merge(client[["client_id", "gender", "birth_date"]], on="client_id", how="left"))
    a = a.merge(owner, on="account_id", how="left")
    n_tanpa_owner = int(a["client_id"].isna().sum())
    log.info("CEK      akun tanpa OWNER: %d", n_tanpa_owner)

    lahir = pd.to_datetime(a["birth_date"])
    buka = a["tgl_buka"]
    belum_ultah = (buka.dt.month < lahir.dt.month) | (
        (buka.dt.month == lahir.dt.month) & (buka.dt.day < lahir.dt.day))
    umur = buka.dt.year - lahir.dt.year - belum_ultah.astype(int)       # umur saat akun dibuka
    a["kelompok_umur_pemilik"] = pd.cut(umur, bins=UMUR_BINS, labels=UMUR_LABEL).astype(object)
    a["gender_pemilik"] = a["gender"].map({"M": "Laki-laki", "F": "Perempuan"})

    a["frekuensi"] = a["frequency"]
    for c in ["frekuensi", "nama_distrik", "region", "gender_pemilik", "kelompok_umur_pemilik"]:
        a[c] = a[c].fillna(TIDAK_DIKETAHUI)
    a["tgl_buka"] = a["tgl_buka"].dt.date

    a = a.sort_values("account_id").reset_index(drop=True)
    a.insert(0, "sk_akun", range(1, len(a) + 1))
    return a[["sk_akun", "account_id", "frekuensi", "tgl_buka", "nama_distrik", "region",
              "rata_gaji", "tingkat_pengangguran", "gender_pemilik", "kelompok_umur_pemilik"]]


def clean_trans(trans: pd.DataFrame) -> pd.DataFrame:
    t = trans.copy()
    for c in ["type", "operation", "k_symbol"]:
        t[c] = t[c].astype("string").str.strip().replace("", pd.NA).fillna(TIDAK_DIKETAHUI).astype(object)
    return t


def build_dim_jenis_transaksi(t: pd.DataFrame) -> pd.DataFrame:
    j = (t[["type", "operation", "k_symbol"]].drop_duplicates()
         .sort_values(["type", "operation", "k_symbol"]).reset_index(drop=True)
         .rename(columns={"type": "tipe", "operation": "operasi"}))
    j.insert(0, "sk_jenis_trx", range(1, len(j) + 1))
    return j


def build_dim_status_pinjaman(loan: pd.DataFrame) -> pd.DataFrame:
    kode = sorted(loan["status"].dropna().astype(str).str.strip().unique())
    rows = [(k, *STATUS_PINJAMAN.get(k, (TIDAK_DIKETAHUI, TIDAK_DIKETAHUI))) for k in kode]
    s = pd.DataFrame(rows, columns=["kode_status", "deskripsi", "kategori"])
    s.insert(0, "sk_status", range(1, len(s) + 1))
    return s


# ==========================================================================
# TRANSFORM - fakta (lookup surrogate key + reject)
# ==========================================================================
def split_reject(df: pd.DataFrame, key_cols: list, nama: str) -> pd.DataFrame:
    """Baris dengan FK kosong ditulis ke file reject, sisanya dikembalikan."""
    gagal = df[key_cols].isna().any(axis=1)
    if gagal.any():
        rej = df[gagal].copy()
        rej["alasan"] = rej[key_cols].isna().apply(
            lambda r: "tidak ada di " + ", ".join(c for c in key_cols if r[c]), axis=1)
        path = config.LOG_DIR / f"reject_{nama}_{RUN_TS}.csv"
        rej.to_csv(path, index=False)
        log.warning("REJECT   %s: %d baris -> %s", nama, len(rej), path.name)
    return df[~gagal].copy()


def build_fact_transaksi(t, dim_akun, dim_waktu, dim_jenis) -> tuple:
    f = (t.merge(dim_akun[["sk_akun", "account_id"]], on="account_id", how="left")
          .merge(dim_jenis, left_on=["type", "operation", "k_symbol"],
                 right_on=["tipe", "operasi", "k_symbol"], how="left"))
    f["id_waktu"] = pd.to_datetime(f["date"]).dt.strftime("%Y%m%d").astype(int)
    f.loc[~f["id_waktu"].isin(dim_waktu["id_waktu"]), "id_waktu"] = np.nan
    f["jumlah_bertanda"] = np.where(f["type"].isin(TIPE_MASUK), f["amount"], -f["amount"])
    f = f.rename(columns={"amount": "jumlah", "balance": "saldo"})
    keys = ["sk_akun", "id_waktu", "sk_jenis_trx"]
    lolos = split_reject(f, keys, "fact_transaksi")
    lolos[keys] = lolos[keys].astype(int)
    return lolos[["trans_id", *keys, "jumlah", "saldo", "jumlah_bertanda"]], len(f) - len(lolos)


def build_fact_pinjaman(loan, dim_akun, dim_waktu, dim_status) -> tuple:
    p = loan.copy()
    p["status"] = p["status"].astype(str).str.strip()
    p = (p.merge(dim_akun[["sk_akun", "account_id"]], on="account_id", how="left")
          .merge(dim_status[["sk_status", "kode_status"]], left_on="status", right_on="kode_status", how="left"))
    p["id_waktu"] = pd.to_datetime(p["date"]).dt.strftime("%Y%m%d").astype(int)
    p.loc[~p["id_waktu"].isin(dim_waktu["id_waktu"]), "id_waktu"] = np.nan
    p = p.rename(columns={"amount": "jumlah_pinjaman", "duration": "durasi_bulan", "payments": "cicilan_bulanan"})
    keys = ["sk_akun", "id_waktu", "sk_status"]
    lolos = split_reject(p, keys, "fact_pinjaman")
    lolos[keys] = lolos[keys].astype(int)
    return lolos[["loan_id", *keys, "jumlah_pinjaman", "durasi_bulan", "cicilan_bulanan"]], len(p) - len(lolos)


def transform(src: dict) -> dict:
    t = clean_trans(src["trans"])
    out = {
        "dim_waktu": build_dim_waktu(src["trans"], src["loan"]),
        "dim_akun": build_dim_akun(src["account"], src["district"], src["disp"], src["client"]),
        "dim_jenis_transaksi": build_dim_jenis_transaksi(t),
        "dim_status_pinjaman": build_dim_status_pinjaman(src["loan"]),
    }
    out["fact_transaksi"], out["_reject_trx"] = build_fact_transaksi(
        t, out["dim_akun"], out["dim_waktu"], out["dim_jenis_transaksi"])
    out["fact_pinjaman"], out["_reject_pinjaman"] = build_fact_pinjaman(
        src["loan"], out["dim_akun"], out["dim_waktu"], out["dim_status_pinjaman"])
    for name in LOAD_ORDER:
        log.info("TRANSFORM %-20s %7d baris", name, len(out[name]))
    return out


# ==========================================================================
# LOAD
# ==========================================================================
LOAD_ORDER = ["dim_waktu", "dim_akun", "dim_jenis_transaksi", "dim_status_pinjaman",
              "fact_transaksi", "fact_pinjaman"]


def load(out: dict, dw_engine: Engine) -> None:
    """Full refresh (SCD tipe 1) dalam SATU transaksi: gagal di tengah -> rollback, DW tetap utuh."""
    with dw_engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(f"dw.{t}" for t in LOAD_ORDER) + " CASCADE"))
        for t in LOAD_ORDER:
            out[t].to_sql(t, conn, schema="dw", if_exists="append", index=False,
                          method="multi", chunksize=1000)
            log.info("LOAD     dw.%-20s %7d baris", t, len(out[t]))


def validate(src: dict, out: dict, dw_engine: Engine) -> str:
    """Rekonsiliasi: baris DW + baris reject harus sama dengan baris sumber."""
    with dw_engine.connect() as conn:
        n_tr = conn.execute(text("SELECT COUNT(*) FROM dw.fact_transaksi")).scalar()
        n_ln = conn.execute(text("SELECT COUNT(*) FROM dw.fact_pinjaman")).scalar()
        sum_tr = conn.execute(text("SELECT COALESCE(SUM(jumlah),0) FROM dw.fact_transaksi")).scalar()
    ok = (n_tr + out["_reject_trx"] == len(src["trans"])
          and n_ln + out["_reject_pinjaman"] == len(src["loan"])
          and (out["_reject_trx"] > 0 or float(sum_tr) == float(src["trans"]["amount"].sum())))
    msg = (f"fact_transaksi {n_tr} (+{out['_reject_trx']} reject) dari {len(src['trans'])}; "
           f"fact_pinjaman {n_ln} (+{out['_reject_pinjaman']} reject) dari {len(src['loan'])}; "
           f"total jumlah transaksi {float(sum_tr):,.0f} -> {'COCOK' if ok else 'TIDAK COCOK'}")
    log.info("VALIDASI %s", msg)
    if not ok:
        raise ValueError("Rekonsiliasi gagal: " + msg)
    return msg


def write_etl_log(dw_engine: Engine, mulai, status, ket) -> None:
    try:
        with dw_engine.begin() as conn:
            conn.execute(text("INSERT INTO dw.etl_log (mulai, selesai, status, keterangan) "
                              "VALUES (:mulai, :selesai, :status, :ket)"),
                         {"mulai": mulai, "selesai": datetime.now(), "status": status, "ket": ket[:2000]})
    except Exception as e:  # log ETL tidak boleh menggagalkan proses
        log.warning("Gagal menulis dw.etl_log: %s", e)


def main() -> int:
    mulai = datetime.now()
    log.info("=" * 60)
    log.info("ETL dimulai")
    src_engine = create_engine(config.db_url(config.SOURCE_DB))
    dw_engine = create_engine(config.db_url(config.DW_DB))
    try:
        src = extract(src_engine)          # E: SQL + CSV
        load_staging(src, dw_engine)
        out = transform(src)               # T: pandas
        load(out, dw_engine)               # L: to_sql
        msg = validate(src, out, dw_engine)
        log.info("ETL SUKSES dalam %.1f detik", (datetime.now() - mulai).total_seconds())
        write_etl_log(dw_engine, mulai, "SUKSES", msg)
        return 0
    except Exception as e:
        log.exception("ETL GAGAL: %s", e)
        write_etl_log(dw_engine, mulai, "GAGAL", str(e))
        return 1
    finally:
        src_engine.dispose()
        dw_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
