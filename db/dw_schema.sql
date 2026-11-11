CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS mart;

DROP VIEW  IF EXISTS mart.v_transaksi, mart.v_pinjaman;
DROP TABLE IF EXISTS dw.fact_transaksi, dw.fact_pinjaman,
                     dw.dim_waktu, dw.dim_wilayah, dw.dim_nasabah, dw.dim_rekening,
                     dw.dim_jenis_transaksi, dw.dim_status_pinjaman CASCADE;
                     
CREATE TABLE dw.dim_waktu (
    waktu_key     INTEGER PRIMARY KEY,
    tanggal       DATE NOT NULL UNIQUE,
    hari          SMALLINT NOT NULL,
    nama_hari     VARCHAR(10) NOT NULL,
    bulan         SMALLINT NOT NULL,
    nama_bulan    VARCHAR(10) NOT NULL,
    kuartal       SMALLINT NOT NULL,
    semester      SMALLINT NOT NULL,
    tahun         SMALLINT NOT NULL,
    tahun_bulan   CHAR(7) NOT NULL
);

CREATE TABLE dw.dim_wilayah (
    wilayah_key            INTEGER PRIMARY KEY,
    district_id            INTEGER NOT NULL UNIQUE,
    nama_district          VARCHAR(50) NOT NULL,
    region                 VARCHAR(50) NOT NULL,
    jumlah_penduduk        INTEGER,
    jumlah_kota            SMALLINT,
    rasio_penduduk_kota    NUMERIC(5,1),
    rata_gaji              INTEGER,
    pengangguran_95        NUMERIC(5,2),
    pengangguran_96        NUMERIC(5,2),
    wirausaha_per_1000     INTEGER,
    kejahatan_95           INTEGER,
    kejahatan_96           INTEGER
);

CREATE TABLE dw.dim_nasabah (
    nasabah_key        INTEGER PRIMARY KEY,
    client_id          INTEGER NOT NULL UNIQUE,
    gender             VARCHAR(10) NOT NULL,
    tanggal_lahir      DATE NOT NULL,
    umur               SMALLINT NOT NULL,
    kelompok_umur      VARCHAR(10) NOT NULL,
    district_domisili  VARCHAR(50),
    region_domisili    VARCHAR(50)
);

CREATE TABLE dw.dim_rekening (
    rekening_key        INTEGER PRIMARY KEY,
    account_id          INTEGER NOT NULL UNIQUE,
    frekuensi_laporan   VARCHAR(30) NOT NULL,
    tanggal_buka        DATE NOT NULL,
    tahun_buka          SMALLINT NOT NULL,
    jumlah_pemegang     SMALLINT NOT NULL,
    punya_disponent     BOOLEAN NOT NULL,
    jenis_kartu         VARCHAR(20) NOT NULL
);

CREATE TABLE dw.dim_jenis_transaksi (
    jenis_transaksi_key INTEGER PRIMARY KEY,
    kode_tipe           VARCHAR(10) NOT NULL,
    tipe_transaksi      VARCHAR(30) NOT NULL,
    kode_operasi        VARCHAR(20),
    operasi             VARCHAR(40) NOT NULL,
    kode_keterangan     VARCHAR(20),
    keterangan          VARCHAR(40) NOT NULL,
    arah                VARCHAR(6)  NOT NULL
);

CREATE TABLE dw.dim_status_pinjaman (
    status_key       INTEGER PRIMARY KEY,
    kode_status      CHAR(1) NOT NULL UNIQUE,
    keterangan       VARCHAR(60) NOT NULL,
    status_kontrak   VARCHAR(10) NOT NULL,
    kualitas_kredit  VARCHAR(12) NOT NULL
);

CREATE TABLE dw.fact_transaksi (
    transaksi_key        BIGSERIAL,
    trans_id             INTEGER NOT NULL,
    waktu_key            INTEGER NOT NULL REFERENCES dw.dim_waktu(waktu_key),
    rekening_key         INTEGER NOT NULL REFERENCES dw.dim_rekening(rekening_key),
    nasabah_key          INTEGER NOT NULL REFERENCES dw.dim_nasabah(nasabah_key),
    wilayah_key          INTEGER NOT NULL REFERENCES dw.dim_wilayah(wilayah_key),
    jenis_transaksi_key  INTEGER NOT NULL REFERENCES dw.dim_jenis_transaksi(jenis_transaksi_key),
    bank_mitra           VARCHAR(10) NOT NULL,
    jumlah               NUMERIC(14,2) NOT NULL,
    jumlah_bertanda      NUMERIC(14,2) NOT NULL,
    saldo                NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (transaksi_key, waktu_key)
) PARTITION BY RANGE (waktu_key);

CREATE TABLE dw.fact_transaksi_1993 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19930101) TO (19940101);
CREATE TABLE dw.fact_transaksi_1994 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19940101) TO (19950101);
CREATE TABLE dw.fact_transaksi_1995 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19950101) TO (19960101);
CREATE TABLE dw.fact_transaksi_1996 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19960101) TO (19970101);
CREATE TABLE dw.fact_transaksi_1997 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19970101) TO (19980101);
CREATE TABLE dw.fact_transaksi_1998 PARTITION OF dw.fact_transaksi FOR VALUES FROM (19980101) TO (19990101);
CREATE TABLE dw.fact_transaksi_lain PARTITION OF dw.fact_transaksi DEFAULT;

CREATE INDEX ix_ft_rekening ON dw.fact_transaksi (rekening_key);
CREATE INDEX ix_ft_wilayah  ON dw.fact_transaksi (wilayah_key);
CREATE INDEX ix_ft_jenis    ON dw.fact_transaksi (jenis_transaksi_key);

CREATE TABLE dw.fact_pinjaman (
    loan_id           INTEGER NOT NULL UNIQUE,
    waktu_key         INTEGER NOT NULL REFERENCES dw.dim_waktu(waktu_key),
    rekening_key      INTEGER NOT NULL REFERENCES dw.dim_rekening(rekening_key),
    nasabah_key       INTEGER NOT NULL REFERENCES dw.dim_nasabah(nasabah_key),
    wilayah_key       INTEGER NOT NULL REFERENCES dw.dim_wilayah(wilayah_key),
    status_key        INTEGER NOT NULL REFERENCES dw.dim_status_pinjaman(status_key),
    jumlah_pinjaman   NUMERIC(14,2) NOT NULL,
    durasi_bulan      SMALLINT NOT NULL,
    cicilan_bulanan   NUMERIC(12,2) NOT NULL,
    flag_bermasalah   SMALLINT NOT NULL,
    PRIMARY KEY (rekening_key, waktu_key)
);

CREATE INDEX ix_fp_wilayah ON dw.fact_pinjaman (wilayah_key);
CREATE INDEX ix_fp_status ON dw.fact_pinjaman (status_key);

CREATE VIEW mart.v_transaksi AS
SELECT f.trans_id,
       w.tanggal, w.tahun, w.kuartal, w.bulan, w.nama_bulan, w.tahun_bulan,
       r.account_id, r.frekuensi_laporan, r.jenis_kartu,
       n.client_id, n.gender, n.kelompok_umur,
       wl.nama_district, wl.region,
       j.tipe_transaksi, j.operasi, j.keterangan, j.arah,
       f.bank_mitra, f.jumlah, f.jumlah_bertanda, f.saldo
FROM dw.fact_transaksi f
JOIN dw.dim_waktu           w  ON w.waktu_key  = f.waktu_key
JOIN dw.dim_rekening        r  ON r.rekening_key = f.rekening_key
JOIN dw.dim_nasabah         n  ON n.nasabah_key  = f.nasabah_key
JOIN dw.dim_wilayah         wl ON wl.wilayah_key = f.wilayah_key
JOIN dw.dim_jenis_transaksi j  ON j.jenis_transaksi_key = f.jenis_transaksi_key;

CREATE VIEW mart.v_pinjaman AS
SELECT f.loan_id,
       w.tanggal, w.tahun, w.kuartal, w.bulan, w.nama_bulan, w.tahun_bulan,
       r.account_id, r.frekuensi_laporan, r.jenis_kartu,
       n.client_id, n.gender, n.umur, n.kelompok_umur,
       wl.nama_district, wl.region, wl.rata_gaji, wl.pengangguran_96,
       s.kode_status, s.keterangan AS status_pinjaman, s.status_kontrak, s.kualitas_kredit,
       f.jumlah_pinjaman, f.durasi_bulan, f.cicilan_bulanan, f.flag_bermasalah
FROM dw.fact_pinjaman f
JOIN dw.dim_waktu           w  ON w.waktu_key  = f.waktu_key
JOIN dw.dim_rekening        r  ON r.rekening_key = f.rekening_key
JOIN dw.dim_nasabah         n  ON n.nasabah_key  = f.nasabah_key
JOIN dw.dim_wilayah         wl ON wl.wilayah_key = f.wilayah_key
JOIN dw.dim_status_pinjaman s  ON s.status_key = f.status_key;