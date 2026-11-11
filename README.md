# Data Warehouse Bank (PKDD'99 Financial)

ETL dengan **Python + SQLAlchemy**, data warehouse di **PostgreSQL**, dan dashboard di **Apache Superset**.
Semua berjalan langsung di komputer (tanpa Docker). Konfigurasi disimpan di satu file **`.env`**.

---

## 1. Gambaran Umum

### Arsitektur (Data Warehouse dengan Staging Area dan Data Mart)

```
 SUMBER                 STAGING AREA          DATA WAREHOUSE (bank_dw.dw)        DATA MART (bank_dw.mart)    PENGGUNA
 bank_oltp (SQL) ─┐                            dim_waktu   dim_wilayah
  client account  ├─► Extract ─► staging.* ─►  dim_nasabah dim_rekening    ─►   v_transaksi            ─►  Apache Superset
  disp loan trans │   (pandas)   Transform     dim_jenis_transaksi             v_pinjaman                  (dashboard)
 CSV (flat file) ─┘              (pandas)      dim_status_pinjaman
  district card order            Load          fact_transaksi (partisi/tahun)
                                 (SQLAlchemy)  fact_pinjaman
```

| Lapisan | Isi |
|---|---|
| Sumber | Database `bank_oltp` (client, account, disp, loan, trans) dan file CSV (district, card, order) |
| Staging | Schema `staging` berisi salinan mentah hasil ekstraksi (`stg_*`) |
| Data warehouse | Schema `dw` dengan skema **fact constellation (galaxy)**: 2 tabel fakta berbagi dimensi |
| Data mart | Schema `mart` berisi view datar per proses bisnis untuk Superset |

### Proses bisnis

| Proses | Tabel fakta | Grain | Measure |
|---|---|---|---|
| Transaksi rekening | `fact_transaksi` | 1 transaksi pada 1 rekening | `jumlah`, `jumlah_bertanda`, `saldo` |
| Pemberian pinjaman | `fact_pinjaman` | 1 pinjaman | `jumlah_pinjaman`, `durasi_bulan`, `cicilan_bulanan`, `flag_bermasalah` |

Dimensi bersama: `dim_waktu`, `dim_rekening`, `dim_nasabah`, `dim_wilayah`.
Dimensi khusus: `dim_jenis_transaksi` (transaksi) dan `dim_status_pinjaman` (pinjaman).

---

## 2. Prasyarat

| Software | Versi | Catatan |
|---|---|---|
| PostgreSQL + `psql` | 14+ (diuji di 16) | Server berjalan di `localhost:5432` |
| Python (ETL) | 3.10+ | Python sistem (termasuk 3.14) bisa dipakai |
| Python (Superset) | **3.11** | Superset **tidak bisa** dipasang di Python 3.12+. Gunakan `uv` untuk mendapatkan Python 3.11 tanpa mengubah Python sistem |
| `uv` | terbaru | Pengelola Python & paket: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

## 3. Struktur Folder

```
data_warehouse/
├── .env                      # konfigurasi (jangan di-commit ke git)
├── .env.example              # template .env
├── .gitignore
├── requirements.txt          # dependency ETL
├── README.md
├── data/
│   ├── sql/                  # 01_client.sql 02_account.sql 03_disp.sql 04_loan.sql 05_trans.sql
│   └── csv/                  # district.csv card.csv order.csv
├── db/
│   ├── setup.sql             # membuat database + mengisi seed (dijalankan via psql)
│   ├── oltp_schema.sql       # DDL database sumber
│   └── dw_schema.sql         # DDL staging, dw, mart
├── etl/
│   ├── config.py             # membaca .env
│   ├── extract.py            # SQL + CSV -> staging
│   ├── transform.py          # cleansing, terjemahan kode, dimensi, fakta
│   ├── load.py               # full load + validasi
│   └── main.py               # menjalankan pipeline ETL
└── superset/
    └── superset_config.py    # konfigurasi Superset (membaca .env)
```

> `setup.sql` **harus** berada di folder `db/`, karena perintah `\ir` di dalamnya mencari file lain relatif terhadap lokasinya.

---

## 4. Konfigurasi `.env`

Salin template, lalu isi password dan secret key:

```bash
cp .env.example .env
```

```
# PostgreSQL
DB_PASSWORD=isi_dengan_string

# Apache Superset
SUPERSET_KEY=isi_dengan_string
```

## 5. Langkah Menjalankan

Semua perintah dijalankan dari folder proyek.

> **Pengguna fish shell:** perintah di bawah memakai sintaks bash. Lihat [bagian 6](#6-catatan-untuk-fish-shell) untuk padanannya di fish.

### Langkah 1 — Buat database (sekali saja)

```bash
psql -h localhost -p 5432 -U postgres -d postgres -f db/setup.sql
```

Script ini melakukan tiga hal:
1. Menghapus lalu membuat ulang database `bank_oltp` dan `bank_dw`.
2. Membuat tabel sumber dan mengisi data seed (`data/sql/01..05_*.sql`, urutannya mengikuti foreign key).
3. Membuat schema `staging`, `dw` (dimensi, fakta, partisi), dan `mart` (view) di `bank_dw`.

Pesan `NOTICE: ... does not exist, skipping` **bukan error**. Artinya perintah `DROP ... IF EXISTS` tidak menemukan objek lama, jadi dilewati.

Cek hasilnya:
```bash
psql -h localhost -U postgres -d bank_oltp -c "SELECT COUNT(*) FROM trans;"   # 79208
psql -h localhost -U postgres -d bank_dw   -c "\dt dw.*"                      # tabel dimensi & fakta
psql -h localhost -U postgres -d bank_dw   -c "\dv mart.*"                    # v_transaksi, v_pinjaman
```

> Peringatan: menjalankan `setup.sql` lagi akan **menghapus isi kedua database**. Setelahnya, jalankan ETL ulang.
> Untuk membuat ulang skema DW saja: `psql -h localhost -U postgres -d bank_dw -f db/dw_schema.sql`

### Langkah 2 — Siapkan Python untuk ETL

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Langkah 3 — Jalankan ETL

```bash
source venv/bin/activate
python3 etl/main.py
```

Pastikan keempat baris validasi berstatus **[OK]**:
```
=== Validate ===
Validasi trans -> fact_transaksi : source=79208 dw=79208.0 [OK]
Validasi loan -> fact_pinjaman   : source=682 dw=682.0 [OK]
Validasi total amount transaksi  : ... [OK]
Validasi total amount pinjaman   : ... [OK]
```

Cek isi data mart:
```bash
psql -h localhost -U postgres -d bank_dw -c "SELECT COUNT(*) FROM mart.v_transaksi;"   # 79208
psql -h localhost -U postgres -d bank_dw -c "SELECT COUNT(*) FROM mart.v_pinjaman;"    # 682
```

ETL aman dijalankan berulang kali. Tabel DW dikosongkan lalu diisi ulang dalam satu transaksi.

### Langkah 4 — Instal Apache Superset

Superset dipasang di venv **terpisah** dengan **Python 3.11**:

```bash
uv venv --python 3.11 venv-superset
source venv-superset/bin/activate
python --version                      # harus Python 3.11.x

uv pip install "apache-superset==5.0.0" psycopg2-binary \
    cachetools rich "flask-caching<2.4" "setuptools<81" Pillow
```

Selain `apache-superset`, perintah ini memasang beberapa paket lain:
* `psycopg2-binary`: driver PostgreSQL.
* `cachetools`, `rich`, `Pillow`: dependency yang tidak ikut terpasang otomatis.
* `flask-caching<2.4` dan `setuptools<81`: mengunci versi supaya cocok dengan Superset.

Inisialisasi:
```bash
set -a; source .env; set +a

superset db upgrade
superset fab create-admin --username admin --firstname Admin --lastname DW \
    --email admin@example.com --password admin
superset init
```

Kalau berhasil, `superset db upgrade` diawali baris `Loaded your LOCAL configuration at [superset/superset_config.py]` dan diakhiri log migrasi `alembic`.

### Langkah 5 — Jalankan Superset

Lakukan setiap kali ingin membuka dashboard:
```bash
source venv-superset/bin/activate
set -a; source .env; set +a
superset run -h 0.0.0.0 -p 8088 --with-threads
```

Biarkan terminal tetap terbuka, lalu buka **http://localhost:8088** dan login dengan `admin` / `admin`. Tekan `Ctrl + C` untuk menghentikan Superset.

---

## 6. Catatan untuk fish shell

Di fish, perintah `set -a; source .env` dan `source venv/bin/activate` tidak berlaku.

**Membuat perintah `loadenv` (sekali saja):**
```fish
function loadenv
    for line in (string match -rv '^\s*(#|$)' < .env)
        set -l kv (string split -m 1 '=' -- (string trim -c \r -- $line))
        set -gx $kv[1] $kv[2]
    end
end
funcsave loadenv
```

| Bash | Fish |
|---|---|
| `source venv/bin/activate` | `source venv/bin/activate.fish` |
| `source venv-superset/bin/activate` | `source venv-superset/bin/activate.fish` |
| `set -a; source .env; set +a` | `loadenv` |
| `export X=1` | `set -gx X 1` |
| `source ~/.bashrc` (setelah instal uv) | `fish_add_path ~/.local/bin` |

**Menjalankan Superset di fish:**
```fish
cd ~/Documents/lab/data_warehouse
source venv-superset/bin/activate.fish
loadenv
superset run -h 0.0.0.0 -p 8088 --with-threads
```

---

## 7. Membuat Dashboard di Superset

Superset baru selalu kosong. Data baru muncul setelah langkah a–c berikut.

### a. Hubungkan database

1. Pilih **Settings → Database Connections → + Database → PostgreSQL**.
2. Klik *Connect this database with a SQLAlchemy URI string instead*.
3. Isi:
   ```
   Display Name   : bank_dw
   SQLAlchemy URI : postgresql+psycopg2://postgres:PASSWORD_ANDA@localhost:5432/bank_dw
   ```
4. Klik **Test Connection**, lalu **Connect**.

### b. Buat dataset

Pilih **Datasets → + Dataset**, database `bank_dw`, schema `mart`, lalu buat dua dataset:
* `v_transaksi`
* `v_pinjaman`

Di dataset `v_pinjaman`, tambahkan *saved metric* lewat **Edit dataset → Metrics → + Add item**:

| Nama | SQL |
|---|---|
| `rasio_bermasalah` | `100.0 * SUM(flag_bermasalah) / COUNT(*)` |

### c. Buat chart

**Dashboard Transaksi Rekening** (dataset `v_transaksi`):

| No | Chart | Tipe | Pengaturan |
|---|---|---|---|
| 1 | Total Nilai Transaksi | Big Number | Metric: `SUM(jumlah)` |
| 2 | Jumlah Transaksi | Big Number | Metric: `COUNT(*)` |
| 3 | Tren Nilai Transaksi per Bulan | Line Chart | X-axis: `tanggal` (Time grain: Month), Metric: `SUM(jumlah)`, Dimensions: `arah` |
| 4 | Nilai Transaksi per Region | Bar Chart | X-axis: `region`, Metric: `SUM(jumlah)`, Dimensions: `tipe_transaksi` (stacked) |
| 5 | Komposisi Jenis Operasi | Pie Chart | Dimension: `operasi`, Metric: `COUNT(*)` |
| 6 | Keterangan Transaksi per Tahun | Pivot Table | Rows: `keterangan`, Columns: `tahun`, Metric: `SUM(jumlah)` |
| 7 | Arus Kas Bersih per Tahun | Bar Chart | X-axis: `tahun`, Metric: `SUM(jumlah_bertanda)` |
| 8 | Uang Masuk vs Keluar per Tahun | Bar Chart | X-axis: `tahun`, Metric: `SUM(jumlah)`, Dimensions: `arah` |

**Dashboard Pemberian Pinjaman** (dataset `v_pinjaman`):

| No | Chart | Tipe | Pengaturan |
|---|---|---|---|
| 1 | Total Pinjaman Disalurkan | Big Number | Metric: `SUM(jumlah_pinjaman)` |
| 2 | Jumlah Pinjaman | Big Number | Metric: `COUNT(*)` |
| 3 | Rasio Kredit Bermasalah (%) | Big Number | Metric: `rasio_bermasalah` |
| 4 | Rasio Kredit Bermasalah per Region | Bar Chart | X-axis: `region`, Metric: `rasio_bermasalah`, urutkan descending |
| 5 | Rasio Bermasalah per Kelompok Umur & Gender | Bar Chart | X-axis: `kelompok_umur`, Dimensions: `gender`, Metric: `rasio_bermasalah` |
| 6 | Pinjaman per Tahun & Status | Bar Chart (stacked) | X-axis: `tahun`, Metric: `SUM(jumlah_pinjaman)`, Dimensions: `status_pinjaman` |
| 7 | Distribusi Status Pinjaman | Pie Chart | Dimension: `status_pinjaman`, Metric: `COUNT(*)` |
| 8 | Rata-rata Pinjaman per Durasi | Bar Chart | X-axis: `durasi_bulan`, Metric: `AVG(jumlah_pinjaman)` |

Simpan setiap chart dengan **Save → Add to dashboard**.

### d. Filter dashboard

Di dashboard, buka panel **Filters → + Add filter**, lalu buat filter untuk `tahun`, `region`, `gender`, dan `jenis_kartu`. Terapkan ke semua chart.
