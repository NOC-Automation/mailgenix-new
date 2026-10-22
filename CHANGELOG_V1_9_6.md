# MailGenix v1.9.6 - Sequence Management

## Added
- New **Sequence Management** workspace available to both Admin and User roles.
- Sequence types: EQM, ESG, WAF, AVE, RTA, SFR, DAC, SAC, and POC.
- EQM activities: IN / OUT. Other activities follow the selected sequence type.
- Automatic sequence format: `[TYPE]/[SITE]-[COUNTER]/[ROMAN_MONTH]/[YEAR]`.
- JKT2 site code `2` and JKT3 site code `3`.
- Independent counters scoped by **Type + Site + Month + Year**.
- Monthly counter reset to `001`.
- Tenant List customer integration with site-aware searchable customer selection.
- Sequence summary cards for Total This Month, each supported type, and Sequence Lainnya.
- Search and filters for Type, Activity, Site, lifecycle Status, Document Status, Month, and Year.
- Right-side **Add Sequence Drawer** with live sequence preview.
- Automatic **Approved By** from the logged-in account.
- Document Status options: Linked, Printed, Tenant List, QR Already Sent & Tenant List.
- Editable operational fields and a dedicated Sequence Audit Log.
- Active / Void lifecycle with mandatory reason when a sequence is voided.
- 15-second lightweight live-state polling so multi-user sequence changes appear without full-page reload.

## Sequence integrity rules
- An issued Sequence Number is immutable.
- Sequence Type, Site, Approved By, and Sequence Number are locked after creation.
- Used numbers are never reused, including numbers belonging to VOID records.
- Incorrect Type or Site must be handled by VOID-ing the old record and creating a new sequence.
- Editing another operational field never renumbers any existing sequence.
- Final sequence allocation is performed by the backend inside a database transaction; the drawer preview is informational until Create Sequence succeeds.

## Editable after issue
- Activity
- Customer
- Ticket Number
- Document Status
- EQM Saved
- Operational Date
- Remarks

> Changing Operational Date after issue does not change the already-issued Sequence Number.
