# MailGenix v1.9.1 - Migration 0008 Fix

## Fix
- Fixed Django 5.2.8 compatibility in `core/migrations/0008_customer_additional_mailing_list.py`.
- `QuerySet.iterator()` now provides `chunk_size=500` after `prefetch_related()`.
- This fixes: `ValueError: chunk_size must be provided when using QuerySet.iterator() after prefetch_related()`.

## Upgrade from failed v1.9 migration
If `core.0008_customer_additional_mailing_list` failed and remains unapplied, replace the source with this revision and run:

```powershell
python manage.py showmigrations core
python manage.py migrate
```

No `--fake`, rollback, database deletion, or manual schema changes are required when `0008` is still shown as `[ ]`.
