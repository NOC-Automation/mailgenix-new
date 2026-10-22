# MailGenix UI v2

## Responsive frontend rebuild
- Rebuilt Tailwind CSS from the current templates and JavaScript sources.
- Replaced the legacy white menu shell with a corporate navy responsive sidebar.
- Added mobile navigation drawer and backdrop.
- Reworked top navigation and user menu.
- Added stable CSS fallbacks for dashboard, Tenant Workspace, and Mailing List layouts.
- Dashboard now uses 4/2/1 KPI breakpoints and 2-column content layout on large screens.
- Notification Template Gallery now renders 3/2/1 cards per row.
- Email Composer now renders 3/2/1 sections per row.
- Tenant Customer Workspace now uses larger typography, balanced spacing, and responsive sidebar/detail layout.
- Fixed stale `hidden` state behavior so customer empty state and detail content cannot appear simultaneously.
- Improved table readability and Support Group editor spacing.

## v1.6.1 - Edit AR Group & Customer Mailing List
- Fixed Customer Workspace edit flow to carry the correct `group_id` and `rack_id`.
- Added fallback to persist the backend-resolved `group_id` during edit prefill.
- Added per-location Edit action to avoid ambiguous edits for multi-site/multi-rack customers.
- Restored optional Customer Mailing List on Add/Edit Customer.
- Existing mailing-list memberships are prefilled on edit.
- Added Mailing List column/chips in Customer Workspace Authorized Persons.
- Bulk Site/Floor and Mailing Group recipient behavior remains independent and resolves customer recipients to BCC.
