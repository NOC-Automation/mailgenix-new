# MailGenix v1.9.3

## Support Group CSV & User CRUD

- Added Support Group CSV import in Customer Workspace.
- Added Support Group CSV template download.
- Authenticated `user` role can Add, Edit, Delete, and CSV Import Support Group data.
- User Management and other admin-only operations remain admin-only.
- CSV location fields can be blank; when provided, `site`, `floor`, and `rack` must all match a location already registered to the selected customer.
- Import uses update-or-create matching customer + name + identity number + email/phone + rack to reduce exact duplicate entries.
- Activity Log records Support Group CSV imports.
