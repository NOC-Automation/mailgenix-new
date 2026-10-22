# MailGenix v1.9.5 - PM + Variant Footer Revision

This package is still application version v1.9.5. It updates the Notification Template / Email Composer behavior only and does not add a new database migration.

## Local upgrade

1. Back up your current `automation/db.sqlite3`.
2. Extract this package to a new folder.
3. Copy the existing `db.sqlite3` to the new `automation/` folder if you want to retain your local data.
4. Create the local environment file before running Django:

```powershell
cd automation
Copy-Item .env.local.example .env.local
```

5. Activate your existing Python 3.12 virtual environment.
6. Run:

```powershell
py manage.py check
py manage.py migrate
py manage.py showmigrations core
```

The final migration remains:

```text
[X] 0012_changelog_v195
```

7. Start the app:

```powershell
py manage.py runserver 127.0.0.1:8080
```

Normal browser refresh is sufficient; v1.9.5 static assets use cache-busting.

## Recommended PM test

1. Mailing List -> Preventive Maintenance -> General.
2. Enter Ticket Number and Site.
3. Enter a Maintenance Period.
4. Add at least three activities in an intentionally unsorted order, for example:
   - UPS G / Quarterly / `27 - 28 October 2026` / Yes
   - Vesda / Monthly / `08 October 2026` / No
   - CRAC / Quarterly / `16 - 19 & 20 - 21 October 2026` / Yes
5. Confirm Preview sorts them as Vesda -> CRAC -> UPS G.
6. Confirm Service Impact is `No Impact to IT Load`.
7. Confirm No MOP renders `-` and Yes renders `MOP Attached`.
8. Test General, A100 and BOND and confirm each footer changes automatically.
9. Generate `.eml` and open it in Outlook to verify HTML, recipients and embedded logo.
