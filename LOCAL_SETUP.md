# MailGenix Local Setup (Windows, no Docker)

Recommended Python: 3.12.x

## 1. Open PowerShell in the extracted project folder

Example:

```powershell
cd C:\Users\Administrator\Documents\project\Mailgenix\mailgenix-vercel-ready
```

## 2. Create virtual environment `sans`

```powershell
py -3.12 -m venv sans
```

Activate it:

```powershell
.\sans\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\sans\Scripts\Activate.ps1
```

## 3. Install local dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\automation\requirements.local.txt
```

The runtime requirements no longer include NumPy/Pandas because the Django app does not use them. This also avoids the Python 3.14 NumPy compiler issue encountered earlier.

## 4. Local environment configuration

`automation/.env.local` is already configured for SQLite. If it is missing:

```powershell
Copy-Item .\automation\.env.local.example .\automation\.env.local
```

You do not need to manually set `$env:DB_ENGINE` each time.

## 5. Run checks and migrations

```powershell
cd .\automation
python manage.py check
python manage.py migrate
```

## 6. Create an administrator

```powershell
python manage.py createsuperuser
```

## 7. Run MailGenix

```powershell
python manage.py runserver 127.0.0.1:8080
```

Open:

`http://127.0.0.1:8080`

## Shortcut

From the repository root you can also run:

```powershell
.\run_local.bat
```

The script creates/uses `sans`, installs dependencies, migrates SQLite, and starts Django.
