#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
[ -f automation/.env.local ] || cp automation/.env.local.example automation/.env.local
[ -x sans/bin/python ] || python3.12 -m venv sans
source sans/bin/activate
python -m pip install --upgrade pip
python -m pip install -r automation/requirements.local.txt
cd automation
python manage.py migrate
python manage.py runserver 127.0.0.1:8080
