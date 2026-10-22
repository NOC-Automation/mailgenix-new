# Upgrade MailGenix v1.9.6 → v1.9.7 Corrected

Use branch `develop-v1.9.7`. This corrected package preserves the v1.9.6 Sequence schema.

From repository root on Windows PowerShell:

```powershell
git branch --show-current
git status
.\venv\Scripts\Activate.ps1
cd .\automation
pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations core
python manage.py migrate --plan
```

Expected new migration chain:
- `0014_v197_operational_refinement`
- `0015_v197_remote_hands`
- `0016_changelog_v197`

Do not run `migrate` unless `makemigrations --check --dry-run` reports `No changes detected` and the plan does not recreate `SequenceCounter`, `SequenceRecord`, or `SequenceAuditLog`.
