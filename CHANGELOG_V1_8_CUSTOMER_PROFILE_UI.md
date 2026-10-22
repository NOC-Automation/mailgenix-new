# MailGenix v1.8.0 — Unified Customer Profile & UI

## Customer / Tenant
- Removed Customer View / Table View toggle; Customer Workspace is now the only Tenant List view.
- Header `Import CSV` now opens the working import modal directly.
- Add/Edit Tenant redesigned as one customer profile:
  - Customer Information: Customer Name + Office Phone only.
  - Dynamic `+ Add Location / Rack` rows (Site, Floor, Rack).
  - Dynamic `+ Add Authorized Person` rows.
  - Authorized Person is customer-wide and no longer assigned to a rack.
- AR validity status is calculated automatically from Validity Date:
  - Active: > 30 days remaining
  - Expiring Soon: 0–30 days remaining
  - Expired: date has passed
- Added `AR.validity` and `AR.due_date` fields and migration `0006_ar_profile_validity.py`.
- Existing v1.7 AR validity data is copied from ARGroup during migration.

## CSV Import
- Repeated customer names create/reuse one customer and add multiple rack locations.
- Repeated AR email for the same customer is deduplicated.
- A location-only row is supported by leaving all Authorized Person columns blank.
- `validity` accepts `Valid`, `Active`, `Expiring Soon`, or `Expired`.
- Optional `mailing_list` column is supported with `;` separator.

## Recipient Resolver
- Site/Floor and Mailing Group first match impacted customers by their rack locations.
- All non-expired Authorized Persons for matching customers are used as recipients.
- Specific Customer -> TO.
- Site/Floor bulk -> BCC.
- Mailing Group -> BCC.

## Mailing List UI
- Removed the small decorative/logo box beside notification-template titles.
- Removed `Go` from each template card.
- Each template card now has only `Preview Template`.
- Previewing a template also selects it in the Email Composer.
- Final composer action renamed to `Generate Draft`.

## UI
- Added consistent illustrated-style cards, form sections, tables, modal, spacing, responsive behavior, and mobile layouts across the primary operational pages.
