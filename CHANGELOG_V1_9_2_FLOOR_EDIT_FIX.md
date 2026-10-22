# MailGenix v1.9.2 — Floor Edit Fix

## Fixed

- Fixed Add/Edit Tenant Floor dropdown rendering after CSV import.
- `tenant_add.html` expects `floor_levels`, while the view previously only exposed `floor_levels_distinct`.
- The tenant add-page context now exposes both keys for backward compatibility.
- Imported FloorLevel rows are now available as options when editing a customer profile.

## Upgrade

No database migration is required for this patch.
After replacing the source, restart Django and hard-refresh the browser (`Ctrl+Shift+R`).
