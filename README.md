# MailGenix v1.5

MailGenix is a Django-based customer notification and operational workflow automation application.

## Current development features

- Corporate split-screen login
- Dashboard operational KPIs
- Customer status: Active / Expiring Soon / Expired
- Dynamic Authorized Persons by customer location/rack
- Customer-centric Tenant Workspace
- Support Group CRUD
- Notification template gallery and HTML preview
- Outlook `.eml` generation with CID embedded images
- Location-aware recipient resolution
- Site/Floor bulk recipient resolution to BCC
- Mailing List Group presets (JKT2 General, JKT2 MP36, PM Level 7) to BCC
- Specific Customer recipient resolution to TO
- Activity Log visible to all authenticated users
- Changelog / What's New visible to all authenticated users
- CSV import for customer + dynamic Authorized Person rows
- Local SQLite support
- Vercel/PostgreSQL support through `DATABASE_URL`

## Environment model

- Local: SQLite using `automation/.env.local`
- GitHub: source code only; local env/database are ignored
- Vercel: PostgreSQL using Vercel Environment Variables

## Start here

Read `FULL_SETUP_GUIDE.md` for the complete Local -> GitHub -> Vercel workflow.

For the latest feature changes, read:

- `CHANGELOG_V1_5.md`
- `CHANGELOG_SUPPORT_GROUP_WORKSPACE.md`
- `CHANGELOG_RECIPIENT_RULES.md`

## UI v2 responsive rebuild
The current package includes `CHANGELOG_UI_V2.md` and `automation/frontend/templates/static/css/mailgenix-ui-v2.css`.
The UI v2 stylesheet is loaded after legacy styles to stabilize the responsive layout across local and Vercel deployments.


## v1.7 Dynamic Mailing Group
Admin dapat mengelola Mailing Group dari sidebar berdasarkan Site + beberapa Floor. Membership customer dihitung otomatis dari lokasi; tidak perlu memilih grouping saat membuat customer.

## v1.8 Customer Profile Workflow
Tenant List now uses a single Customer Workspace (the legacy Table View toggle is removed). Add/Edit Tenant supports multiple Site/Floor/Rack rows in one customer profile, while Authorized Persons belong to the customer as a whole. Validity display status is derived automatically from each Authorized Person's validity date.

After upgrading from v1.7 run `python manage.py migrate` to apply `0006_ar_profile_validity`.

## v1.9 Customer Additional Mailing Lists

Additional Mailing Lists are customer-level email addresses, separate from Authorized Persons and Dynamic Mailing Groups.

- Specific Customer: active Authorized Persons -> TO; Additional Mailing Lists -> CC.
- Site/Floor bulk: active Authorized Persons + Additional Mailing Lists of matching customers -> BCC.
- Dynamic Mailing Group bulk: active Authorized Persons + Additional Mailing Lists of matching customers -> BCC.
- Deduplication priority: TO > CC > BCC.
- Add/Edit Tenant section 4 manages Additional Mailing Lists.
- CSV optional column: `additional_mailing_list`, with multiple addresses separated by semicolons.
- Run `python manage.py migrate` to apply migrations 0008 and 0009.

## v1.9.3 - Support Group CSV & User CRUD

- Support Group can be created, edited, and deleted by authenticated Admin and User roles.
- Support Group CSV import is available from the selected customer's Support Group tab.
- Downloadable Support Group CSV template is available in the UI.
- Customer CSV import and User Management keep their existing admin restrictions.

## v1.9.4 - UI, Recipient Scope & Session Refinements

- Support Group CSV Template and Import CSV are Admin-only; authenticated User can still Add/Edit/Delete Support Group manually.
- Tenant Site Groups use collapsible accordions with browser-persisted state.
- Dashboard spacing, Changelog, and Support Group status visuals were refined.
- Mailing Group floors are natural-sorted and the Add/Edit interface has improved spacing and selection states.
- Mailing List uses explicit Recipient Scope modes: Site/Floor, Specific Customer, Mailing Group.
- Mailing Group resolution shows matched customers, active AR, additional mailing-list count, and unique BCC count.
- Resolved TO/CC/BCC are read-only but selectable/copyable and vertically resizable.
- User Management displays only Admin/User roles; Staff/Superuser columns are removed from the UI.
- Session cookie lifetime is 24 hours with HttpOnly, SameSite=Lax, persistent browser sessions, and Secure cookies when production settings are used.
- Run `python manage.py migrate` to apply `0011_changelog_v194`.

## v1.9.6 - Sequence Management
MailGenix v1.9.6 adds monthly automatic Sequence Management for EQM, ESG, WAF, AVE, RTA, SFR, DAC, SAC, and POC, with Tenant List integration, immutable issued numbers, Admin/User operational access, VOID handling, audit history, and live multi-user refresh. See `CHANGELOG_V1_9_6.md` and `UPGRADE_V1_9_6.md`.
# mailgenix-new
# mailgenix-new
# mailgenix-new
