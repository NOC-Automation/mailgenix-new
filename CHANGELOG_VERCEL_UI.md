# UI & Vercel Change Log

## Dashboard / Tenant List
- Added `customer_count`, `authorized_person_count`, and `rack_count` to dashboard context.
- Added dashboard summary cards.
- Added visible Total Customer indicator in Tenant List header.

## Login
- Rebuilt login as a formal corporate split-screen page.
- Added "Selamat datang di MailGenix" branding panel.
- Uses the existing NTT DATA email logo asset instead of the missing `static/img/logo.png` path.
- Removed dead password-reset/register links that had no corresponding routes.

## Mailing List
- Increased spacing between Notification Gallery cards and composer fields.
- Split composer visually into Notification Scope and Recipient Selection.
- Changed resolved recipient display to a multiline textarea for long mailing lists.
- Existing JavaScript element IDs and workflow are preserved.

## Vercel
- Added `DATABASE_URL` PostgreSQL support with `dj-database-url`.
- Local fallback is SQLite.
- Added `.vercel.app` support plus automatic `VERCEL_URL` handling.
- Added `.python-version` (3.12).
- Added `.env.vercel.example`.
- Slimmed runtime dependencies.
- AWS GitHub Actions deploy is now manual (`workflow_dispatch`) in this development copy.
