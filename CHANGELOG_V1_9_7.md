# MailGenix v1.9.7 — Reports, Checklist Compliance & Operational Refinement

## Corrected upgrade baseline
This package is built directly on MailGenix v1.9.6 and preserves the existing Sequence Management schema (`SequenceCounter`, `SequenceRecord`, `SequenceAuditLog`).

## Added
- Admin-only Sequence Excel report with NTT logo.
- Sequence Number click-to-copy.
- Admin-only Sequence Audit and Void actions.
- Customer Associations: Contractor/WAF and Visitor/AVE.
- Mailing Group explicit customer inclusion.
- Checklist JKT2/JKT3 workspace, compliance tracking, BOND schedules/evidence, Mizuho A3/B1 daily requirements.
- Admin-only Checklist Excel report with NTT logo.
- Remote Hands report module with PDF/DOCX export.
- Dashboard Customer Validity donut data and Tenant Distribution by Site data.
- Notification formatting refinements and dynamic EML filename.

## Compatibility
- Migration chain continues from `0013_sequence_management_v196`.
- No v1.9.7 migration recreates or deletes existing Sequence tables.
