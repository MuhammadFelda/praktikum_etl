#!/usr/bin/env bash
# Dipanggil oleh Cron. Contoh crontab (setiap hari jam 01:00):
#   0 1 * * * /path/ke/etl-perbankan/run_etl.sh >> /path/ke/etl-perbankan/logs/cron.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
if [ -d venv ]; then source venv/bin/activate; fi
python3 etl.py
