# Upgrade MailGenix v1.9.4 -> v1.9.5

1. Back up `automation/db.sqlite3` and your environment file.
2. Extract v1.9.5 and restore the existing database when retaining local data.
3. Activate the Python 3.12 virtual environment.
4. From `automation/` run:

```powershell
py manage.py check
py manage.py migrate
py manage.py showmigrations core
```

Expected new migration:

```text
[X] 0011_changelog_v194
[X] 0012_changelog_v195
```

5. Start MailGenix:

```powershell
py manage.py runserver 127.0.0.1:8080
```

v1.9.5 static assets use versioned URLs, so a normal page refresh is sufficient after deployment; Ctrl+Shift+R should no longer be required for this release.
