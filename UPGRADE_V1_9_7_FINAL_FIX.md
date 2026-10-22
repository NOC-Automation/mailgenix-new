# Upgrade v1.9.7 Corrected -> Final Stabilization Patch

This patch is application/UI focused and does not add a new database migration. Existing 0014-0016 remain unchanged.

After copying the patch into the develop-v1.9.7 branch:

```powershell
cd automation
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations core
python manage.py runserver
```

Expected: `No changes detected`. Re-test Sequence add/edit/audit/void, Login invalid credentials, Mailing Group floor filtering, Tenant WAF/AVE tabs, all checklists, Remote Hands multi-photo/caption and EML filename.
