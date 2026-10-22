# MailGenix v1.5 - Local, GitHub, and Vercel Setup

This package is intentionally one codebase for three environments:

- **Local**: Django + SQLite
- **GitHub**: source/version control only (no secrets and no SQLite database)
- **Vercel**: Django + PostgreSQL via `DATABASE_URL`

The application decides which database to use automatically:

- if `DATABASE_URL` exists -> PostgreSQL
- otherwise -> SQLite from `.env.local`

## A. Run locally on Windows (recommended Python 3.12)

### 1. Extract the ZIP

Example:

`C:\Users\Administrator\Documents\project\Mailgenix\mailgenix-v1.5`

Open PowerShell in the extracted root directory.

### 2. Verify Python 3.12

```powershell
py -0p
py -3.12 --version
```

If Python 3.12 is not installed, install it first. This project intentionally uses Python 3.12 for compatibility with its pinned dependencies.

### 3. Create the virtual environment named `sans`

```powershell
py -3.12 -m venv sans
```

Activate it:

```powershell
.\sans\Scripts\Activate.ps1
```

If PowerShell blocks scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\sans\Scripts\Activate.ps1
```

Verify:

```powershell
python --version
(Get-Command python).Source
```

Expected: Python 3.12.x and a path ending in `sans\Scripts\python.exe`.

### 4. Install local dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\automation\requirements.local.txt
```

### 5. Local environment

The package already contains:

`automation\.env.local`

with local-only settings similar to:

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=mailgenix-local-development-only-change-me
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
APP_ENV=local
EMAIL_SENDING_ENABLED=False
```

You do not need to manually type `$env:DB_ENGINE=...` anymore.

### 6. Run Django checks and migrations

```powershell
cd .\automation
python manage.py check
python manage.py migrate
```

The local SQLite database is created as:

`automation\db.sqlite3`

### 7. Create the first admin user

```powershell
python manage.py createsuperuser
```

The password is typed invisibly in the terminal; that is normal.

### 8. Start MailGenix

```powershell
python manage.py runserver 127.0.0.1:8080
```

Open:

`http://127.0.0.1:8080`

or:

`http://localhost:8080`

### 9. Subsequent local runs

From the root directory:

```powershell
.\sans\Scripts\Activate.ps1
cd .\automation
python manage.py runserver 127.0.0.1:8080
```

After pulling code that contains new migrations:

```powershell
python manage.py migrate
```

### 10. Shortcut

From the project root you can also run:

```powershell
.\run_local.bat
```

It creates `sans` if necessary, installs dependencies, runs migrations, and starts the development server.

---

## B. Test checklist before GitHub/Vercel

Test with dummy data first:

1. Login as admin.
2. Create Customer A with multiple site/floor/rack records.
3. Create different Authorized Persons for different locations.
4. Add, edit, and delete Support Group records.
5. Confirm customer badges: Active / Expiring Soon / Expired.
6. Confirm Dashboard totals and Recent Activity.
7. Confirm Activity Log is visible from a normal user account.
8. Confirm Changelog is visible from a normal user account.
9. Generate a notification and verify it appears in Activity Log.
10. Open the generated `.eml` in Outlook and confirm the embedded logo appears.
11. Test Specific Customer recipient resolution -> location ARs in TO.
12. Test Site/Floor bulk -> location ARs in BCC.
13. Test Mailing List Group preset -> matching group ARs in BCC.

---

## C. Prepare a GitHub repository

### 1. Do not commit local secrets/data

The included `.gitignore` excludes:

- `automation/.env.local`
- `db.sqlite3` / `*.sqlite3`
- `sans/`
- `.venv/`
- Python cache
- `.sql` backups

Before the first commit, confirm:

```powershell
cd ..
git status
```

Make sure `db.sqlite3`, `.env.local`, and `sans` are not staged.

### 2. Create a new staging/development GitHub repository

For safety, use a separate repository such as:

`mailgenix-santos`

or:

`mailgenix-staging`

This package changes the existing AWS deployment workflow to **manual `workflow_dispatch` only**, so a normal Git push does not automatically modify the existing AWS production server.

### 3. Initialize Git locally

From the project root:

```powershell
git init
git add .
git status
git commit -m "MailGenix v1.5 staging baseline"
git branch -M main
```

### 4. Connect GitHub

Replace the URL with your repository:

```powershell
git remote add origin https://github.com/YOUR-ORG/mailgenix-staging.git
git push -u origin main
```

### 5. Normal update workflow

```powershell
git status
git add .
git commit -m "Describe the MailGenix change"
git push origin main
```

Never commit database passwords, Django secret keys, or production `.env` files.

---

## D. Create PostgreSQL for Vercel

SQLite is local-only. Vercel needs persistent external PostgreSQL.

A practical staging choice is Supabase.

### 1. Create a separate Supabase project

Do not point Vercel staging at the existing AWS production database.

### 2. Get two PostgreSQL connection strings from Supabase `Connect`

Recommended use:

- **Migrations from your Windows machine**: Direct connection if reachable, otherwise Session Pooler on port `5432`.
- **Vercel/serverless application traffic**: Transaction Pooler on port `6543` is designed for transient/serverless connections. If you experience ORM/driver compatibility issues, use the Session Pooler on port `5432` instead.

Both should use SSL (`sslmode=require`).

---

## E. Initialize the hosted PostgreSQL database

Do this from your trusted local machine with the `sans` environment active.

### 1. Enter the Django folder

```powershell
cd .\automation
```

### 2. Temporarily point Django to the hosted database

Use the migration/session connection string:

```powershell
$env:DATABASE_URL="postgresql://...:5432/postgres?sslmode=require"
$env:DJANGO_SECRET_KEY="temporary-management-secret"
$env:DJANGO_DEBUG="False"
```

### 3. Install production PostgreSQL dependency if it is not already in the local venv

```powershell
python -m pip install -r requirements.txt
```

### 4. Run checks and migrations

```powershell
python manage.py check
python manage.py migrate
```

### 5. Create the Vercel/staging superuser

```powershell
python manage.py createsuperuser
```

This user is created in PostgreSQL, not in your local SQLite database.

### 6. Remove the temporary environment variables

```powershell
Remove-Item Env:DATABASE_URL
Remove-Item Env:DJANGO_SECRET_KEY
Remove-Item Env:DJANGO_DEBUG
```

After removal, local Django returns to SQLite via `.env.local`.

---

## F. Deploy GitHub to Vercel

Current Vercel Django support recognizes `manage.py` and discovers the WSGI application automatically.

### 1. In Vercel

Choose:

`Add New -> Project -> Import Git Repository`

Select the staging GitHub repository.

### 2. Set Root Directory

Set the Vercel **Root Directory** to:

`automation`

This is critical because `manage.py` is inside that folder.

### 3. Framework/build settings

Do not add old `/api` Django routing hacks or redirects. Leave the framework/build behavior at the Vercel defaults for Django unless Vercel explicitly asks otherwise.

The package contains:

- `automation/manage.py`
- `automation/.python-version` = `3.12`
- `automation/requirements.txt`

### 4. Add Vercel Environment Variables

Go to:

`Project -> Settings -> Environment Variables`

Add:

```text
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DATABASE_URL=<Vercel/serverless PostgreSQL connection URL>
DJANGO_ALLOWED_HOSTS=.vercel.app
```

Optional custom domain:

```text
DJANGO_ALLOWED_HOSTS=.vercel.app,mailgenix.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://mailgenix.example.com
```

`VERCEL_URL` is supplied by Vercel and the project settings automatically add it to Django allowed hosts/trusted origins.

### 5. Generate a strong Django secret locally

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output into Vercel as `DJANGO_SECRET_KEY`.

### 6. Deploy

Click **Deploy**.

If environment variables were added after a deployment, redeploy so they take effect.

### 7. First online test

Open the generated `*.vercel.app` URL and test:

- login
- Dashboard
- Tenant List/customer workspace
- Support Group CRUD
- Activity Log
- Changelog
- Mailing List recipient resolution
- notification preview
- `.eml` download + embedded image

Do not import the complete customer dataset until these tests pass.

---

## G. Key environment differences

### Local

```text
Source code + automation/.env.local -> SQLite
```

Run:

```powershell
python manage.py runserver 127.0.0.1:8080
```

### GitHub

```text
Source code only
No .env.local
No db.sqlite3
No passwords/secrets
```

### Vercel

```text
GitHub source + Vercel Environment Variables -> PostgreSQL
```

No source-code edits are needed when switching from local to Vercel.

---

## H. Safety notes

1. Keep Vercel staging database separate from AWS production.
2. Keep AWS production deployment manual until staging is proven.
3. Test migrations against staging first.
4. Never upload/commit `.env`, database passwords, API keys, or production backups.
5. Activity Log is intentionally viewable by all authenticated users but should not expose raw secret values or full email bodies.
6. Changelog is viewable by all authenticated users; publishing new app releases can be managed in Django Admin.
