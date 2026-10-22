@echo off
setlocal
cd /d %~dp0
if not exist automation\.env.local copy automation\.env.local.example automation\.env.local >nul
if not exist sans\Scripts\python.exe py -3.12 -m venv sans
call sans\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r automation\requirements.local.txt
cd automation
python manage.py migrate
python manage.py runserver 127.0.0.1:8080
