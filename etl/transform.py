import logging
import pandas as pd
from config import TANGGAL_ACUAN_UMUR

log = logging.getLogger(__name__)

TIPE_TRANSAKSI = {
    "PRIJEM": "Kredit (uang masuk)",
    "VYDAJ": "Debit (uang keluar)",
    "VYBER": "Penarikan tunai",
}
OPERASI = {
    "VYBER KARTOU": "Penarikan kartu kredit",
    "VKLAD": "Setoran tunai",
    "PREVOD Z UCTU": "Transfer masuk dari bank lain",
    "VYBER": "Penarikan tunai",
    "PREVOD NA UCET": "Transfer keluar ke bank lain",
}
KETERANGAN = {
    "POJISTNE": "Pembayaran asuransi",
    "SLUZBY": "Biaya laporan rekening",
    "UROK": "Bunga diterima",
    "SANKC. UROK": "Denda bunga saldo negatif",
    "SIPO": "Pembayaran rumah tangga",
    "DUCHOD": "Dana pensiun",
    "UVER": "Cicilan pinjaman",
    "LEASING": "Leasing",
}
FREKUENSI = {
    "POPLATEK MESICNE": "Bulanan",
    "POPLATEK TYDNE": "Mingguan",
    "POPLATEK PO OBRATU": "Setelah transaksi",
}
STATUS_PINJAMAN = [
    # kode, keterangan, status_kontrak, kualitas_kredit
    ("A", "Kontrak selesai, tidak ada masalah", "Selesai", "Lancar"),
    ("B", "Kontrak selesai, pinjaman tidak dibayar", "Selesai", "Bermasalah"),
    ("C", "Kontrak berjalan, pembayaran lancar", "Berjalan", "Lancar"),
    ("D", "Kontrak berjalan, nasabah berutang", "Berjalan", "Bermasalah"),
]
NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]
URUTAN_KARTU = {"gold": 3, "classic": 2, "junior": 1}
TIDAK_ADA = "Tidak ada keterangan"

def _clean_str(s: pd.Series) -> pd.Series:
    """Trim spasi; string kosong / spasi saja -> NA."""
    s = s.astype("string").str.strip()
    return s.mask(s == "")

def _to_waktu_key(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.strftime("%Y%m%d").astype(int)

def _add_surrogate_key(df: pd.DataFrame, key: str) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df.insert(0, key, range(1, len(df) + 1))
    return df

def _kelompok_umur(umur: pd.Series) -> pd.Series:
    bins = [0, 24, 34, 44, 54, 64, 200]
    labels = ["<25", "25-34", "35-44", "45-54", "55-64", "65+"]
    return pd.cut(umur, bins=bins, labels=labels).astype(str)

def _lookup(df: pd.DataFrame, col: str, mapping: pd.Series, name: str) -> pd.Series:
    """Ganti natural key -> surrogate key; gagal jika ada yang tidak ketemu."""
    result = df[col].map(mapping)
    missing = result.isna().sum()
    if missing:
        raise ValueError(f"{missing} baris gagal lookup {name} (kolom {col})")
    return result.astype(int)

def build_dim_waktu(*date_series: pd.Series) -> pd.DataFrame:
    all_dates = pd.concat([pd.to_datetime(s) for s in date_series])
    start = all_dates.min().replace(month=1, day=1)
    end = all_dates.max().replace(month=12, day=31)
    t = pd.Series(pd.date_range(start, end, freq="D"))
    return pd.DataFrame({
        "waktu_key": t.dt.strftime("%Y%m%d").astype(int),
        "tanggal": t.dt.date,
        "hari": t.dt.day,
        "nama_hari": t.dt.dayofweek.map(lambda i: NAMA_HARI[i]),
        "bulan": t.dt.month,
        "nama_bulan": t.dt.month.map(lambda m: NAMA_BULAN[m - 1]),
        "kuartal": t.dt.quarter,
        "semester": (t.dt.month > 6).astype(int) + 1,
        "tahun": t.dt.year,
        "tahun_bulan": t.dt.strftime("%Y-%m"),
    })

def build_dim_wilayah(district: pd.DataFrame) -> pd.DataFrame:
    d = district.rename(columns={
        "A2": "nama_district", "A3": "region", "A4": "jumlah_penduduk",
        "A9": "jumlah_kota", "A10": "rasio_penduduk_kota", "A11": "rata_gaji",
        "A12": "pengangguran_95", "A13": "pengangguran_96",
        "A14": "wirausaha_per_1000", "A15": "kejahatan_95", "A16": "kejahatan_96",
    })
    for col in ["pengangguran_95", "pengangguran_96", "kejahatan_95", "kejahatan_96",
                "jumlah_penduduk", "rata_gaji", "rasio_penduduk_kota"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")

    n_null = d[["pengangguran_95", "kejahatan_95"]].isna().sum().sum()
    d["pengangguran_95"] = d["pengangguran_95"].fillna(d["pengangguran_96"])
    d["kejahatan_95"] = d["kejahatan_95"].fillna(d["kejahatan_96"])
    log.info("dim_wilayah: %d nilai kosong (1995) diisi dari data 1996", n_null)

    d["nama_district"] = d["nama_district"].str.strip()
    d["region"] = d["region"].str.strip().str.title()
    cols = ["district_id", "nama_district", "region", "jumlah_penduduk", "jumlah_kota",
            "rasio_penduduk_kota", "rata_gaji", "pengangguran_95", "pengangguran_96",
            "wirausaha_per_1000", "kejahatan_95", "kejahatan_96"]
    d = d[cols].sort_values("district_id")
    d["kejahatan_95"] = d["kejahatan_95"].astype(int)
    return _add_surrogate_key(d, "wilayah_key")

def build_dim_nasabah(client: pd.DataFrame, dim_wilayah: pd.DataFrame) -> pd.DataFrame:
    c = client.copy()
    c["tanggal_lahir"] = pd.to_datetime(c["birth_date"])
    acuan = pd.Timestamp(TANGGAL_ACUAN_UMUR)
    c["umur"] = ((acuan - c["tanggal_lahir"]).dt.days // 365.25).astype(int)
    c["kelompok_umur"] = _kelompok_umur(c["umur"])
    c["gender"] = c["gender"].str.strip().map({"M": "Laki-laki", "F": "Perempuan"})

    wil = dim_wilayah.set_index("district_id")
    c["district_domisili"] = c["district_id"].map(wil["nama_district"])
    c["region_domisili"] = c["district_id"].map(wil["region"])
    c["tanggal_lahir"] = c["tanggal_lahir"].dt.date

    cols = ["client_id", "gender", "tanggal_lahir", "umur", "kelompok_umur",
            "district_domisili", "region_domisili"]
    return _add_surrogate_key(c[cols].sort_values("client_id"), "nasabah_key")

def build_dim_rekening(
    account: pd.DataFrame, disp: pd.DataFrame,
    card: pd.DataFrame
) -> pd.DataFrame:
    a = account.copy()
    a["frekuensi_laporan"] = _clean_str(a["frequency"]).map(FREKUENSI).fillna("Lainnya")
    a["tanggal_buka"] = pd.to_datetime(a["date"])
    a["tahun_buka"] = a["tanggal_buka"].dt.year
    a["tanggal_buka"] = a["tanggal_buka"].dt.date

    pemegang = disp.groupby("account_id").agg(
        jumlah_pemegang=("disp_id", "count"),
        punya_disponent=("type", lambda t: (t.str.strip() == "DISPONENT").any()),
    )
    a = a.join(pemegang, on="account_id")

    kartu = card.merge(disp[["disp_id", "account_id"]], on="disp_id")
    kartu["rank"] = kartu["type"].str.strip().map(URUTAN_KARTU)
    kartu = kartu.sort_values("rank").groupby("account_id")["type"].last()
    a["jenis_kartu"] = a["account_id"].map(kartu).str.title().fillna("Tidak punya kartu")

    a["jumlah_pemegang"] = a["jumlah_pemegang"].fillna(0).astype(int)
    a["punya_disponent"] = a["punya_disponent"].fillna(False).astype(bool)
    cols = ["account_id", "frekuensi_laporan", "tanggal_buka", "tahun_buka",
            "jumlah_pemegang", "punya_disponent", "jenis_kartu"]
    return _add_surrogate_key(a[cols].sort_values("account_id"), "rekening_key")

def clean_trans(trans: pd.DataFrame) -> pd.DataFrame:
    t = trans.copy()
    for col in ["type", "operation", "k_symbol", "bank"]:
        t[col] = _clean_str(t[col])
    n_blank = t["k_symbol"].isna().sum()
    log.info("trans: %d k_symbol kosong/NULL -> '%s'", n_blank, TIDAK_ADA)

    t["tipe_transaksi"] = t["type"].map(TIPE_TRANSAKSI).fillna(t["type"])
    t["operasi"] = t["operation"].map(OPERASI).fillna(t["operation"]).fillna("Tidak diketahui")
    t["keterangan"] = t["k_symbol"].map(KETERANGAN).fillna(t["k_symbol"]).fillna(TIDAK_ADA)
    t["arah"] = (t["type"] == "PRIJEM").map({True: "Masuk", False: "Keluar"})
    t["amount"] = pd.to_numeric(t["amount"]).astype(float)
    t["balance"] = pd.to_numeric(t["balance"]).astype(float)
    t["bank_mitra"] = t["bank"].fillna("-")
    return t

def build_dim_jenis_transaksi(trans_clean: pd.DataFrame) -> pd.DataFrame:
    cols = ["type", "tipe_transaksi", "operation", "operasi", "k_symbol", "keterangan", "arah"]
    d = (trans_clean[cols].drop_duplicates()
         .sort_values(["type", "operasi", "keterangan"])
         .rename(columns={"type": "kode_tipe", "operation": "kode_operasi",
                          "k_symbol": "kode_keterangan"}))
    return _add_surrogate_key(d, "jenis_transaksi_key")

def build_dim_status_pinjaman() -> pd.DataFrame:
    d = pd.DataFrame(STATUS_PINJAMAN,
                     columns=["kode_status", "keterangan", "status_kontrak", "kualitas_kredit"])
    return _add_surrogate_key(d, "status_key")

def _key_maps(dims: dict, account: pd.DataFrame, disp: pd.DataFrame) -> dict:
    owner = disp[disp["type"].str.strip() == "OWNER"].set_index("account_id")["client_id"]
    return {
        "rekening": dims["dim_rekening"].set_index("account_id")["rekening_key"],
        "nasabah": dims["dim_nasabah"].set_index("client_id")["nasabah_key"],
        "wilayah": dims["dim_wilayah"].set_index("district_id")["wilayah_key"],
        "owner": owner,                                          # account -> client
        "district_rek": account.set_index("account_id")["district_id"],  # account -> district cabang
    }

def _add_common_keys(f: pd.DataFrame, maps: dict, name: str) -> pd.DataFrame:
    f["waktu_key"] = _to_waktu_key(f["date"])
    f["rekening_key"] = _lookup(f, "account_id", maps["rekening"], f"{name}.rekening")
    f["client_id"] = f["account_id"].map(maps["owner"])
    f["nasabah_key"] = _lookup(f, "client_id", maps["nasabah"], f"{name}.nasabah")
    f["district_id"] = f["account_id"].map(maps["district_rek"])
    f["wilayah_key"] = _lookup(f, "district_id", maps["wilayah"], f"{name}.wilayah")
    return f

def build_fact_transaksi(
    trans_clean: pd.DataFrame, dim_jenis: pd.DataFrame,
    maps: dict
) -> pd.DataFrame:
    f = _add_common_keys(trans_clean.copy(), maps, "fact_transaksi")
    f = f.merge(dim_jenis[["jenis_transaksi_key", "kode_tipe", "operasi", "keterangan"]],
                left_on=["type", "operasi", "keterangan"],
                right_on=["kode_tipe", "operasi", "keterangan"], how="left")
    if f["jenis_transaksi_key"].isna().any():
        raise ValueError("Ada transaksi yang gagal lookup dim_jenis_transaksi")

    f["jumlah"] = f["amount"]
    f["jumlah_bertanda"] = f["amount"].where(f["arah"] == "Masuk", -f["amount"])
    f["saldo"] = f["balance"]
    cols = ["trans_id", "waktu_key", "rekening_key", "nasabah_key", "wilayah_key",
            "jenis_transaksi_key", "bank_mitra", "jumlah", "jumlah_bertanda", "saldo"]
    return f[cols].astype({"jenis_transaksi_key": int}).sort_values("trans_id")

def build_fact_pinjaman(loan: pd.DataFrame, dim_status: pd.DataFrame,
                        maps: dict) -> pd.DataFrame:
    f = _add_common_keys(loan.copy(), maps, "fact_pinjaman")
    f["kode_status"] = f["status"].str.strip()
    f = f.merge(dim_status[["status_key", "kode_status", "kualitas_kredit"]],
                on="kode_status", how="left")
    if f["status_key"].isna().any():
        raise ValueError("Ada pinjaman dengan status tidak dikenal")

    f["jumlah_pinjaman"] = pd.to_numeric(f["amount"]).astype(float)
    f["durasi_bulan"] = f["duration"].astype(int)
    f["cicilan_bulanan"] = pd.to_numeric(f["payments"]).astype(float)
    f["flag_bermasalah"] = (f["kualitas_kredit"] == "Bermasalah").astype(int)
    cols = ["loan_id", "waktu_key", "rekening_key", "nasabah_key", "wilayah_key",
            "status_key", "jumlah_pinjaman", "durasi_bulan", "cicilan_bulanan",
            "flag_bermasalah"]
    return f[cols].sort_values("loan_id")

def transform_all(src: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    trans_clean = clean_trans(src["trans"])

    dims = {}
    dims["dim_waktu"] = build_dim_waktu(src["account"]["date"], src["trans"]["date"],
                                        src["loan"]["date"], src["card"]["issued"])
    dims["dim_wilayah"] = build_dim_wilayah(src["district"])
    dims["dim_nasabah"] = build_dim_nasabah(src["client"], dims["dim_wilayah"])
    dims["dim_rekening"] = build_dim_rekening(src["account"], src["disp"], src["card"])
    dims["dim_jenis_transaksi"] = build_dim_jenis_transaksi(trans_clean)
    dims["dim_status_pinjaman"] = build_dim_status_pinjaman()

    maps = _key_maps(dims, src["account"], src["disp"])
    facts = {
        "fact_transaksi": build_fact_transaksi(trans_clean, dims["dim_jenis_transaksi"], maps),
        "fact_pinjaman": build_fact_pinjaman(src["loan"], dims["dim_status_pinjaman"], maps),
    }
    result = {**dims, **facts}
    for name, df in result.items():
        log.info("Transform    %-20s: %7d baris", name, len(df))
    return result