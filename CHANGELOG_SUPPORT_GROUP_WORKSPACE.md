# MailGenix - Support Group & Customer Workspace

## Tenant List redesign
- Added a customer-centric split layout based on the approved mockup.
- Left panel groups customers by site with search and status badges.
- Customer details render on the same page; selecting a customer does not navigate away or open a detail popup.
- Customer View and legacy Table View can be switched at any time.
- Customer status badges: Active, Expiring Soon (within 30 days), and Expired.

## Customer detail workspace
- Overview with Locations / Racks.
- Authorized Persons (PPOC/SPOC) with location scope and validity.
- Support Group table grouped under each customer.
- Metrics: locations, authorized persons, support group count, and next validity.

## Support Group CRUD
New model fields:
- Name (text)
- NRIC / Passport (text)
- Access Level (text)
- Email / Phone (text)
- Ref: CAR / ESG etc (text)
- Notes (text)
- Rack / location (optional relation)
- Validity (date)
- Status (Active / Expired)

Admin users can create, edit, and delete Support Group records directly inside the customer detail panel without leaving Tenant List.

## Dashboard
- Added Total Support Group.
- Shows Active, Expired, and Registered Today counts.

## Migration
Run:

```bash
python manage.py migrate
```

Migration added: `core/migrations/0003_support_group.py`.
