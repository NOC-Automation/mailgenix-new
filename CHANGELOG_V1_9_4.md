# MailGenix v1.9.4

## Changes

- Support Group CSV Template and Import CSV are visible and accessible only to Admin.
- Normal User role can still add, edit, and delete Support Group data manually.
- Tenant List Site Group headers (for example JKT2/JKT3) are now collapsible accordions and persist their open/closed state in localStorage.
- Dashboard spacing and visual hierarchy were refined, including Changelog and Support Group Status donut/legend.
- Mailing Group floor selectors are naturally sorted (Level 1, Level 2, ..., Level 10) and the Add/Edit UI was restyled.
- Mailing List has explicit Recipient Scope modes: Site/Floor, Specific Customer, and Mailing Group.
- Mailing Group resolver now exposes matched customer, active AR, additional mailing list, and unique BCC counts.
- TO/CC/BCC resolved recipient fields are readonly while remaining selectable/copyable and vertically resizable.
- User Management removes Staff/Superuser display columns and uses Admin/User role badges.
- Session policy is fixed at 24 hours, persists across browser restarts, uses HttpOnly + SameSite=Lax, and uses Secure cookies in production.
