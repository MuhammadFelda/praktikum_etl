-- =====================================================================
-- TARGET: Data Warehouse  -  database bank_dw, schema dw
-- Model  : Fact constellation (2 tabel fakta berbagi dim_waktu & dim_akun)
--   fact_transaksi  grain: satu transaksi
--   fact_pinjaman   grain: satu pinjaman
-- Aturan : surrogate key sk_* dibangkitkan saat ETL, id_waktu = YYYYMMDD,
--          atribut dimensi kosong = 'Tidak diketahui', SCD tipe 1,
--          baris fakta tanpa pasangan dimensi masuk file reject (logs/reject_*.csv)
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;

DROP TABLE IF EXISTS dw.fact_transaksi, dw.fact_pinjaman CASCADE;
DROP TABLE IF EXISTS dw.dim_waktu, dw.dim_akun, dw.dim_jenis_transaksi, dw.dim_status_pinjaman CASCADE;

-- --------------------------- DIMENSI ---------------------------------
CREATE TABLE dw.dim_waktu (
    id_waktu   INTEGER     PRIMARY KEY,                 -- YYYYMMDD (smart key)
    tanggal    DATE        NOT NULL UNIQUE,
    hari       VARCHAR(10) NOT NULL,
    bulan      SMALLINT    NOT NULL CHECK (bulan BETWEEN 1 AND 12),
    kuartal    SMALLINT    NOT NULL CHECK (kuartal BETWEEN 1 AND 4),
    tahun      SMALLINT    NOT NULL
);

CREATE TABLE dw.dim_akun (
    sk_akun               INTEGER      PRIMARY KEY,
    account_id            INTEGER      NOT NULL UNIQUE,  -- business key
    frekuensi             VARCHAR(30)  NOT NULL,
    tgl_buka              DATE         NOT NULL,
    nama_distrik          VARCHAR(50)  NOT NULL,
    region                VARCHAR(50)  NOT NULL,
    rata_gaji             NUMERIC(10,2),
    tingkat_pengangguran  NUMERIC(5,2),                  -- tahun 1996 (district.A13)
    gender_pemilik        VARCHAR(20)  NOT NULL,
    kelompok_umur_pemilik VARCHAR(20)  NOT NULL
);

CREATE TABLE dw.dim_jenis_transaksi (
    sk_jenis_trx  INTEGER     PRIMARY KEY,
    tipe          VARCHAR(20) NOT NULL,
    operasi       VARCHAR(30) NOT NULL,
    k_symbol      VARCHAR(20) NOT NULL,
    CONSTRAINT uq_jenis_trx UNIQUE (tipe, operasi, k_symbol)
);

CREATE TABLE dw.dim_status_pinjaman (
    sk_status    INTEGER     PRIMARY KEY,
    kode_status  VARCHAR(5)  NOT NULL UNIQUE,            -- business key
    deskripsi    VARCHAR(60) NOT NULL,
    kategori     VARCHAR(20) NOT NULL
);

-- ----------------------------- FAKTA ---------------------------------
CREATE TABLE dw.fact_transaksi (
    trans_id         INTEGER       PRIMARY KEY,          -- degenerate dimension
    sk_akun          INTEGER       NOT NULL REFERENCES dw.dim_akun (sk_akun),
    id_waktu         INTEGER       NOT NULL REFERENCES dw.dim_waktu (id_waktu),
    sk_jenis_trx     INTEGER       NOT NULL REFERENCES dw.dim_jenis_transaksi (sk_jenis_trx),
    jumlah           NUMERIC(14,2) NOT NULL,             -- additive
    saldo            NUMERIC(14,2),                      -- semi-additive
    jumlah_bertanda  NUMERIC(14,2) NOT NULL              -- additive (+ masuk, - keluar)
);

CREATE TABLE dw.fact_pinjaman (
    loan_id          INTEGER       PRIMARY KEY,          -- degenerate dimension
    sk_akun          INTEGER       NOT NULL REFERENCES dw.dim_akun (sk_akun),
    id_waktu         INTEGER       NOT NULL REFERENCES dw.dim_waktu (id_waktu),
    sk_status        INTEGER       NOT NULL REFERENCES dw.dim_status_pinjaman (sk_status),
    jumlah_pinjaman  NUMERIC(14,2) NOT NULL,             -- additive
    durasi_bulan     INTEGER       NOT NULL,             -- non-additive
    cicilan_bulanan  NUMERIC(12,2) NOT NULL              -- additive antar pinjaman
);

CREATE INDEX idx_ft_akun   ON dw.fact_transaksi (sk_akun);
CREATE INDEX idx_ft_waktu  ON dw.fact_transaksi (id_waktu);
CREATE INDEX idx_ft_jenis  ON dw.fact_transaksi (sk_jenis_trx);
CREATE INDEX idx_fp_akun   ON dw.fact_pinjaman (sk_akun);
CREATE INDEX idx_fp_waktu  ON dw.fact_pinjaman (id_waktu);
CREATE INDEX idx_fp_status ON dw.fact_pinjaman (sk_status);

-- ------------------------- LOG ETL (operasional) ---------------------
CREATE TABLE IF NOT EXISTS dw.etl_log (
    run_id      SERIAL PRIMARY KEY,
    mulai       TIMESTAMP,
    selesai     TIMESTAMP,
    status      VARCHAR(10),
    keterangan  TEXT
);
