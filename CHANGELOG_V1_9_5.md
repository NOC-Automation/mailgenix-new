# MailGenix v1.9.5

## Main changes
- Redesigned Mailing List into a six-step notification workflow.
- Category / Type / Variant template hierarchy for the 32 supplied source selections.
- Contextual Outage Update Type: Occurrence, Status Update, Recovery, Root Cause.
- Dynamic Outage form and Outlook-friendly HTML email rendering.
- Fault Recovering Time stays visible in the email and renders `-` until Recovery/Root Cause.
- Service Impact is standardized/read-only; standard Additional Information closing text is always preserved.
- Dynamic JKT2/JKT3 subject and location rendering.
- One `.eml` draft carries Subject, TO, CC, BCC, HTML, and CID-embedded logo.
- v1.9.5 cache-busted CSS/JS assets.
- 15-second live-state polling with automatic Tenant/Support Group workspace refresh when safe.

## PM + Variant Footer Revision

- Preventive Maintenance now uses dynamic activity rows (1..N) in Notification Details.
- Each PM activity contains Item (free text), Frequency, Date & Time, and MOP Attached Yes/No.
- Frequency options: Monthly, Quarterly, Semi-Annually, Half-Yearly, Annually, Others.
- PM Remarks are generated automatically: Yes -> `MOP Attached`, No -> `-`.
- PM activities are sorted automatically by their earliest recognizable date before HTML rendering and .eml generation.
- PM Service Impact is read-only and fixed to `No Impact to IT Load`.
- PM Note is optional; blank Note renders as `-`.
- PM Additional Information keeps the standard closing message and places user-entered text above it.
- Variant footer is centralized and rendered automatically:
  - General: `nttapac.id.noc@global.ntt | +62 21-50930-115 | +62 811-1908-0867`
  - A100: `ap.id.myservicedesk@global.ntt | +62 21-50930-116 | +62 811-8816-916`
  - BOND: `ap.id.myservicedesk@global.ntt | +62 21-50930-116 | +62 815-9807-094`
- Changing PM variant no longer recreates the dynamic form, preventing entered PM activities from being cleared.
- No database schema change is required for this revision; migration remains `0012_changelog_v195`.
