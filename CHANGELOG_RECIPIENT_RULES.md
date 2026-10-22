# MailGenix - Recipient & Location Rules

## Implemented business rules

### Location-aware Authorized Person
- AR Group is now linked to a Rack.
- Rack determines Floor and Site.
- The same customer may therefore have different Authorized Persons on different locations.
- The same email address may exist in different AR Groups/locations for one customer; outbound recipients are deduplicated.

Example:

- Customer C / JKT2 / Level 6 -> Andi, Budi
- Customer C / JKT3 / Level 1 -> Citra, Dedi

A JKT2 Level 6 impact resolves Andi and Budi only.

### Recipient placement
- Specific Customer + Site + Floor: matching location ARs -> **TO**.
- Site + Floor bulk: all matching location ARs -> **BCC**.
- Mailing List Group: group recipients -> **BCC** (bulk customer scope).
- Bulk mode keeps the existing NOC address in TO.
- Cross-field deduplication priority: **TO > CC > BCC**.

### Dynamic Mailing List Groups
Groups are resolved from floor rules; customer membership is not manually stored.

- JKT2 General -> JKT2 Level 1-8
- JKT2 MP36 -> JKT2 Level 6-8
- PM Level 7 -> JKT2 Level 7 only

### CSV
The customer import no longer contains `mailing_list` and no longer uses AR1/AR2/AR3 columns.
One CSV row represents one Authorized Person at one customer location.

Header:

`customer_name,customer_site,floor_level,rack_location,validity,due_date,authorized_name,authorized_email,authorized_phone`

### Database migration
Migration `core/migrations/0002_location_scoped_ar_groups.py` adds the ARGroup -> Rack relation and updates uniqueness constraints.

For an existing local database run:

`python manage.py migrate`

Legacy AR Groups are best-effort mapped to the customer's first rack during the migration. Review legacy multi-location customers after migration because the old schema did not contain enough information to infer their original AR location perfectly.
