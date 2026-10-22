# MailGenix v1.9.0 — Customer Additional Mailing Lists

- Additional Mailing List moved from Authorized Person to Customer profile.
- Add/Edit Tenant now has section 4: Additional Mailing Lists.
- Specific Customer recipients: active AR -> TO, customer Additional Mailing Lists -> CC.
- Site/Floor bulk: active AR + Additional Mailing Lists of matching customers -> BCC.
- Dynamic Mailing Group bulk: active AR + Additional Mailing Lists of matching customers -> BCC.
- Cross-field dedupe priority remains TO > CC > BCC.
- CSV preferred optional column is `additional_mailing_list`; values are semicolon-separated email addresses.
- New migration: `0008_customer_additional_mailing_list.py`.
