# MailGenix v1.6.1 — Edit Group & Mailing List Fix

- Fixed Customer Workspace edit URL so it carries `group_id` and `rack_id`.
- Added fallback that stores backend `group_id` during prefill, preventing legacy/bookmarked edit URLs from failing on save.
- Restored optional Customer Mailing List field on Add/Edit Customer.
- Existing mailing-list values are automatically prefilled on edit.
- Multiple mailing-list names can be separated by semicolon (`;`).
- Mailing-list membership is applied to Authorized Persons in the selected AR Group/location.
- Bulk Site/Floor recipient rules remain independent and continue to resolve customer recipients to BCC.
