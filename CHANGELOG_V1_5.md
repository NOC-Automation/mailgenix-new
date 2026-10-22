# MailGenix v1.5.0

## Dashboard & visibility
- Dashboard redesigned around operational KPIs.
- Added customer Active / Expiring Soon / Expired counts.
- Added Authorized Person validity summary.
- Added Support Group active / expired / registered-today summary.
- Added Recent Activity preview.
- Added Activity Log panel visible to all authenticated users.
- Added Changelog / What's New panel visible to all authenticated users.

## Audit trail
- Added append-only `ActivityLog` model.
- Customer create/update/delete activity is mirrored into the audit trail.
- Support Group create/update/delete is logged.
- Customer CSV imports are logged with success/error counts.
- Outlook `.eml` notification generation is logged with notification type, scope, and recipient counts.
- Django Admin can view Activity Log but cannot add/change/delete entries through the admin UI.

## Mailing recipient correction
- Specific Customer + selected location -> matching Authorized Person emails in TO.
- Site/Floor bulk -> matching Authorized Person emails in BCC.
- Mailing List Group (JKT2 General / JKT2 MP36 / PM Level 7) is treated as a bulk site/floor preset -> matching Authorized Person emails in BCC, not CC.
- Cross-field deduplication priority remains TO > CC > BCC.

## Deployment
- Local defaults to SQLite using `automation/.env.local`.
- Hosted environments switch to PostgreSQL when `DATABASE_URL` exists.
- Vercel uses the `automation` directory as project root and detects Django from `manage.py`.
- Production secret key is required when `DJANGO_DEBUG=False`.
- AWS GitHub Action remains manual (`workflow_dispatch`) in this staging package.
