# MailGenix - GitHub & Vercel Deployment Guide

This package is configured for two environments:

- Local development: Django + SQLite
- Vercel: Django + external PostgreSQL via `DATABASE_URL`

## Important safety note

The existing AWS GitHub Actions workflow has been changed to `workflow_dispatch` only. A normal push to `main` will NOT automatically deploy this development copy to the existing EC2 production server.

## Vercel project root

When importing the GitHub repository into Vercel, set **Root Directory** to:

`automation`

Vercel will then see `manage.py` and detect the Django application.

## Required Vercel environment variables

- `DJANGO_SECRET_KEY` - a long random Django secret
- `DJANGO_DEBUG` = `False`
- `DATABASE_URL` - PostgreSQL connection URL
- `DJANGO_ALLOWED_HOSTS` = `.vercel.app`

Optional for a custom domain:

- `DJANGO_ALLOWED_HOSTS` = `.vercel.app,mailgenix.example.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS` = `https://mailgenix.example.com`

Vercel automatically provides `VERCEL_URL`; MailGenix adds that deployment hostname to Django's allowed hosts and trusted origins.

## Database

Do not use SQLite on Vercel for persistent application data. Use an external PostgreSQL database such as Supabase or Neon.

For Supabase, prefer the IPv4-compatible pooler connection. For ORM compatibility, the Session pooler on port 5432 is a conservative choice. Add `?sslmode=require` if it is not already present.

## Initial database setup

Before first production use, run Django migrations against the hosted PostgreSQL database from a trusted local machine:

PowerShell example:

```powershell
cd automation
$env:DATABASE_URL="postgresql://..."
$env:DJANGO_SECRET_KEY="temporary-local-value-for-management-command"
$env:DJANGO_DEBUG="False"
python manage.py migrate
python manage.py createsuperuser
Remove-Item Env:DATABASE_URL
```

Be careful: while `DATABASE_URL` is set, Django management commands operate on the hosted database.

## Static files

The application keeps Django `staticfiles` + WhiteNoise configuration. Current Vercel Django support detects the Django project and serves static assets as part of the deployment.
