# MailGenix Local Development Build

This build is intended for local testing with SQLite and keeps the original production Docker Compose file separate from `docker-compose.local.yml`.

## Included changes

- Dynamic Authorized Person rows on Add/Edit Customer (`+ Add Authorized Person`), with no application-side maximum.
- Edit/update Authorized Person by database ID instead of array position.
- Removed silent AR-group fallback during edit: `group_id` is required for update.
- Mobile Tenant List Edit button now carries `customer_id`, `group_id`, and `rack_id`.
- Clear duplicate AR Group validation before saving validity/due-date changes.
- CSV import normalized to one row per Authorized Person; repeat customer/rack/group fields for unlimited people.
- Notification Template Gallery with `Preview` and `Go` actions.
- Browser preview rewrites the NTT DATA logo to a static URL.
- Outlook `.eml` export embeds the NTT DATA logo as an inline CID MIME image.
- User Management API now correctly returns 403 for non-admin users.
- Added Django tests covering >3 Authorized Persons, ID-based updates, required `group_id`, and user-management authorization.

## Validation performed in this build environment

- All Python files compile successfully (`compileall`).
- All JavaScript files pass `node --check` syntax validation.
- `.eml` MIME structure was generated independently and verified to contain both `cid:mailgenix_ntt_logo` and `Content-ID: <mailgenix_ntt_logo>`.
- Full `manage.py check` / Django test execution could not be run here because this environment cannot download Python packages from PyPI. Docker/local execution remains the recommended runtime verification.
