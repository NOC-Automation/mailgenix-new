# Upgrade MailGenix v1.9.5 -> v1.9.6

MailGenix v1.9.6 adds the Sequence Management module and database tables.

## Windows PowerShell

From the extracted project root:

```powershell
cd automation

# Activate your existing virtual environment first if you use one.
py manage.py check
py manage.py migrate
py manage.py runserver 127.0.0.1:8080
```

Open the local application and select **Sequence Management** from the left sidebar.

## Important
- Migration `0013_sequence_management_v196.py` creates the new sequence tables and publishes the v1.9.6 changelog entry.
- Existing Tenant List data is reused; no customer re-import is required.
- JKT2/JKT3 must already exist in Site Location and customers need rack/location relationships for site-filtered selection.
- Sequence counters reset monthly and are separate for each Type + Site + Month + Year combination.
- Do not copy a production `.env` or production database into local testing unless that is intentional.
