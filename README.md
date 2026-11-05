# ETL Data Warehouse Perbankan (SQLAlchemy + pandas)

Pipeline ETL dari **dua sumber data** (SQL dan CSV) ke data warehouse berbentuk
**fact constellation** di PostgreSQL.

```
 SUMBER 1: SQL  (PostgreSQL bank_oltp)      SUMBER 2: CSV (data/csv_source)
 diisi dari data/postgres_seed/*.sql        district.csv  -> dim_akun
 account, client, disp -> dim_akun          (order.csv & card.csv tidak dipakai model)
 trans                 -> fact_transaksi
 loan                  -> fact_pinjaman
            │ pandas.read_sql                     │ pandas.read_csv
            └──────────────┬──────────────────────┘
                     TRANSFORM (pandas)
                           │  DataFrame.to_sql (SQLAlchemy, 1 transaksi)
                     bank_dw.dw  +  salinan mentah di bank_dw.staging
```

## Model data warehouse

| Tabel | Grain | Key |
|---|---|---|
| `dim_waktu` | satu hari (tanggal terawal–terakhir di `trans` & `loan`) | `id_waktu` = YYYYMMDD |
| `dim_akun` | satu akun (account + district + pemilik dari disp OWNER/client) | `sk_akun`, BK `account_id` |
| `dim_jenis_transaksi` | kombinasi unik tipe–operasi–k_symbol | `sk_jenis_trx` |
| `dim_status_pinjaman` | satu kode status | `sk_status`, BK `kode_status` |
| `fact_transaksi` | satu transaksi | `trans_id` + FK akun, waktu, jenis_trx |
| `fact_pinjaman` | satu pinjaman | `loan_id` + FK akun, waktu, status |

Aturan yang diterapkan ETL:
- Surrogate key `sk_*` dibangkitkan saat ETL; business key tetap disimpan.
- Atribut dimensi kosong diisi `Tidak diketahui` (mis. `k_symbol` kosong/spasi).
- SCD tipe 1: setiap run memuat ulang penuh (truncate + insert) dalam satu transaksi.
- Baris fakta yang tidak punya pasangan di dimensi **tidak dimuat**, tetapi ditulis ke
  `logs/reject_<tabel>_<waktu>.csv` beserta kolom `alasan`.
- Kelompok umur pemilik dihitung **saat akun dibuka**: `<25`, `25-34`, `35-44`, `45-54`, `55+`
  (ubah di konstanta `UMUR_BINS`/`UMUR_LABEL` di `etl.py`).
- `tingkat_pengangguran` memakai tahun 1996 (`district.A13`) karena A12 punya nilai kosong.
- `jumlah_bertanda`: positif untuk `PRIJEM` (uang masuk), negatif untuk `VYDAJ`/`VYBER`.
- Validasi akhir: jumlah baris DW + reject = jumlah baris sumber; hasil dicatat di `dw.etl_log`.

Hasil cek data: tidak ada akun tanpa OWNER, dan tidak ada baris fakta yang di-reject.

## Struktur proyek

```
config.py                    koneksi (.env) & path
etl.py                       script ETL utama
scripts/setup_databases.py   buat bank_oltp + bank_dw, isi sumber SQL, buat skema DW
sql/01_source_oltp.sql       DDL tabel sumber
sql/02_dw_star_schema.sql    DDL physical model data warehouse
data/postgres_seed/*.sql     data sumber SQL (INSERT), jalankan berurutan 01–05
data/csv_source/*.csv        data sumber CSV
run_etl.sh                   wrapper untuk Cron
```

## Cara menjalankan

```bash
pip install -r requirements.txt
cp .env.example .env              # isi user/password PostgreSQL
python scripts/setup_databases.py # sekali saja
python etl.py                     # jalankan ETL (aman diulang)
```

Mengisi sumber SQL secara manual (psql / pgAdmin / DBeaver):

```bash
createdb bank_oltp
psql -d bank_oltp -f sql/01_source_oltp.sql
for f in data/postgres_seed/*.sql; do psql -d bank_oltp -f "$f"; done
```

Penjadwalan Cron (setiap hari jam 01:00):

```
0 1 * * * /path/ke/etl-perbankan/run_etl.sh >> /path/ke/etl-perbankan/logs/cron.log 2>&1
```

## Catatan data

- Deskripsi status pinjaman (A–D) diambil dari dokumentasi dataset PKDD'99 Financial (Berka);
  cocokkan dengan dokumentasi dari dosen sebelum laporan final (konstanta `STATUS_PINJAMAN`).
- Data `trans` hanya berisi 79.208 baris untuk 407 akun dan tidak memuat transaksi bunga
  (`UROK`), jadi `saldo` antar transaksi tidak selalu nyambung. Perlakukan `saldo` sebagai
  semi-additive (rata-rata atau saldo terakhir, jangan dijumlah lintas waktu).

## Contoh query

```sql
-- Pinjaman per region dan kategori status
SELECT a.region, s.kategori, COUNT(*) jml, SUM(f.jumlah_pinjaman) total, AVG(f.durasi_bulan) rata_durasi
FROM dw.fact_pinjaman f
JOIN dw.dim_akun a USING (sk_akun)
JOIN dw.dim_status_pinjaman s USING (sk_status)
GROUP BY 1, 2 ORDER BY 1, 2;

-- Arus kas bersih per kuartal dan kelompok umur pemilik
SELECT w.tahun, w.kuartal, a.kelompok_umur_pemilik, SUM(f.jumlah_bertanda) arus_bersih
FROM dw.fact_transaksi f
JOIN dw.dim_waktu w USING (id_waktu)
JOIN dw.dim_akun a USING (sk_akun)
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
```
