# Upgrade MailGenix v1.9.3 -> v1.9.4

1. Backup your existing `automation/db.sqlite3` before replacing the source folder.
2. Extract v1.9.4 and copy your existing `db.sqlite3` into the new `automation/` folder when you want to retain local data.
3. Activate the Python 3.12 virtual environment.
4. From `automation/`, run:

```powershell
py manage.py check
py manage.py migrate
py manage.py showmigrations core
```

Expected new migration:

```text
[X] 0010_changelog_v193_support_group_csv
[X] 0011_changelog_v194
```

5. Start local server:

```powershell
py manage.py runserver 127.0.0.1:8080
```

6. In the browser use `Ctrl + Shift + R` once to clear old cached CSS/JavaScript.

## v1.9.4 checks

- Admin: Support Group shows CSV Template, Import CSV, Add Support Group.
- User: Support Group shows Add Support Group and Edit/Delete actions, but no CSV controls.
- Tenant List: JKT2/JKT3 site headers can collapse/expand and preserve state.
- Mailing Group: floor list is naturally sorted.
- Mailing List: Site/Floor, Specific Customer, and Mailing Group scopes are mutually exclusive.
- Specific Customer: AR -> TO, Additional Mailing List -> CC.
- Site/Floor and Mailing Group: AR + Additional Mailing List -> BCC.
- Resolved TO/CC/BCC fields are readonly and vertically resizable.
- User Management: Admin/User role badges; no Staff/Superuser columns.
- Session: maximum 24 hours; production cookies remain Secure/HttpOnly/SameSite=Lax.
