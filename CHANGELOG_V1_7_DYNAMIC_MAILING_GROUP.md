# MailGenix v1.7.0 — Dynamic Mailing Group Management

- Added a new **Mailing Group** management source for admins.
- Groups are stored in the database and can be created/edited/deactivated/deleted without code changes.
- Each group selects one Site and one or more Floors.
- Customer membership is resolved automatically from AR Group -> Rack -> Floor -> Site.
- New customers do **not** need to select a Mailing Group manually.
- Existing JKT2 presets are migrated into the new model when JKT2/Floor master data already exists.
- Mailing Group bulk recipients continue to resolve into BCC.
- Specific Customer recipients continue to resolve into TO.
