#!/usr/bin/env bash
set -euo pipefail

VENV_PATH="/home/ubuntu/mailgenix/venv/bin/activate"
ENV_PATH="/home/ubuntu/mailgenix/automation/.env.local"
PROJECT_ROOT="/home/ubuntu/mailgenix/automation"

source "$VENV_PATH"

if [[ ! -f "$ENV_PATH" ]]; then
  echo "[WARN] .env tidak ditemukan. Membuat file baru di: $ENV_PATH"
  touch "$ENV_PATH"
  chmod 0644 "$ENV_PATH"
fi

set -a
source "$ENV_PATH"
set +a

# Sanity check (optional tapi sangat disarankan)
if [[ -z "${DB_PASSWORD:-}" ]]; then
  echo "[ERROR] DB_PASSWORD kosong. Cek isi .env.local"
  exit 1
fi

cd "$PROJECT_ROOT"
exec python3 manage.py runserver 0.0.0.0:8080

