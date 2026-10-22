import re
from collections import defaultdict
from django.db import transaction
from core.models import Customers, AR, ARGroup, EmailLogs

# ============================================================
# CONFIG
# ============================================================
TOP_N = 50                 # tampilkan grup duplikat teratas
FILTER_Q = ""              # isi mis: "AJINOMOTO" untuk fokus, kosongkan untuk semua
MIN_IDS = 2                # minimal jumlah customer_id agar dianggap duplikat

APPLY = False              # <<< PENTING: default False (audit saja)
MIN_OVERLAP_EMAILS = 1     # auto-merge hanya jika overlap email >= ini
KEEP_STRATEGY = "racks"    # "racks" atau "id"

# ============================================================
# NORMALIZATION HELPERS
# ============================================================
def norm_name(s: str) -> str:
    s = (s or "").replace("\u00A0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def norm_email(s: str) -> str:
    return (s or "").strip().lower()

def email_set(customer_id: int):
    emails = set(
        norm_email(e)
        for e in AR.objects.filter(customer_id=customer_id).values_list("email_address", flat=True)
    )
    emails.discard("")
    return emails

def rack_count(customer_id: int) -> int:
    return Customers.objects.get(id=customer_id).racks.count()

def group_count(customer_id: int) -> int:
    return ARGroup.objects.filter(customer_id=customer_id).count()

# ============================================================
# MERGE FUNCTION (merge_id -> keep_id)
# ============================================================
def merge_customers(keep_id: int, merge_id: int, verbose: bool = True):
    if keep_id == merge_id:
        return

    with transaction.atomic():
        keep = Customers.objects.select_for_update().get(id=keep_id)
        merge = Customers.objects.select_for_update().get(id=merge_id)

        # 1) pindahkan rack MERGE -> KEEP
        mr = list(merge.racks.all())
        if mr:
            keep.racks.add(*mr)

        # 2) map group KEEP berdasarkan (validity_AR, due_date)
        keep_groups_map = {(g.validity_AR, g.due_date): g for g in ARGroup.objects.filter(customer=keep)}

        # 3) pindahkan group & AR MERGE -> KEEP
        for mg in ARGroup.objects.filter(customer=merge):
            key = (mg.validity_AR, mg.due_date)
            kg = keep_groups_map.get(key)
            if not kg:
                kg = ARGroup.objects.create(customer=keep, validity_AR=mg.validity_AR, due_date=mg.due_date)
                keep_groups_map[key] = kg

            for a in AR.objects.filter(customer=merge, ar_group=mg).prefetch_related("mailing_lists"):
                email = norm_email(a.email_address)

                if not email:
                    EmailLogs.objects.filter(email_account=a).update(email_account=None)
                    a.delete()
                    continue

                existing = AR.objects.filter(customer=keep, email_address__iexact=email).first()
                if existing:
                    if not (existing.authorized_name or "").strip() and (a.authorized_name or "").strip():
                        existing.authorized_name = a.authorized_name
                    if not (existing.mobile_phone or "").strip() and (a.mobile_phone or "").strip():
                        existing.mobile_phone = a.mobile_phone

                    if existing.ar_group_id != kg.id:
                        existing.ar_group = kg
                    existing.save()

                    mls = list(a.mailing_lists.all())
                    if mls:
                        existing.mailing_lists.add(*mls)

                    EmailLogs.objects.filter(email_account=a).update(email_account=existing)
                    a.delete()
                else:
                    a.customer = keep
                    a.ar_group = kg
                    a.save()

        # 4) pindahkan logs customer MERGE -> KEEP
        EmailLogs.objects.filter(customer=merge).update(customer=keep)

        # 5) hapus MERGE
        ARGroup.objects.filter(customer=merge).delete()
        merge.delete()

    if verbose:
        print(f"APPLIED MERGE: {merge_id} -> {keep_id}")

# ============================================================
# AUDIT + OPTIONAL AUTO-MERGE
# ============================================================
qs = Customers.objects.all().only("id", "name_customer")
if FILTER_Q:
    qs = qs.filter(name_customer__icontains=FILTER_Q)

groups = defaultdict(list)
for c in qs:
    k = norm_name(c.name_customer)
    if k:
        groups[k].append((c.id, c.name_customer or ""))

dup_groups = [(k, v) for k, v in groups.items() if len(v) >= MIN_IDS]
dup_groups.sort(key=lambda kv: len(kv[1]), reverse=True)

print("=========================================")
print("DUPLICATE CUSTOMER AUDIT")
print("Filter:", FILTER_Q or "(none)")
print("Groups total:", len(groups))
print("Duplicate groups:", len(dup_groups))
print("Show top:", min(TOP_N, len(dup_groups)))
print("AUTO MERGE APPLY:", APPLY)
print("AUTO MERGE MIN_OVERLAP_EMAILS:", MIN_OVERLAP_EMAILS)
print("KEEP_STRATEGY:", KEEP_STRATEGY)
print("=========================================")

merged_count = 0

for idx, (key, entries) in enumerate(dup_groups[:TOP_N], start=1):
    ids = [cid for cid, _ in entries]
    raw_names = sorted(set(n for _, n in entries))

    racks = {cid: rack_count(cid) for cid in ids}
    groups_n = {cid: group_count(cid) for cid in ids}
    emails = {cid: email_set(cid) for cid in ids}

    overlap = None
    for s in emails.values():
        overlap = s if overlap is None else overlap.intersection(s)
    overlap = overlap or set()

    pairwise_max = 0
    if len(ids) > 1:
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pairwise_max = max(pairwise_max, len(emails[ids[i]].intersection(emails[ids[j]])))

    print(f"\n[{idx}] norm_name='{key}'")
    print("  raw_names_sample:", raw_names[:3], "..." if len(raw_names) > 3 else "")
    print("  ids:", ids)
    for cid in ids:
        print(f"   - id={cid} racks={racks[cid]} groups={groups_n[cid]} ar_emails={len(emails[cid])}")

    print(f"  overlap_emails_all={len(overlap)}  pairwise_max_overlap={pairwise_max}")
    if overlap:
        print("  overlap_sample:", sorted(list(overlap))[:5])

    if len(overlap) >= MIN_OVERLAP_EMAILS:
        if KEEP_STRATEGY == "racks":
            ids_sorted = sorted(ids, key=lambda cid: (-racks[cid], cid))
        else:
            ids_sorted = sorted(ids)

        keep_id = ids_sorted[0]
        merge_ids = ids_sorted[1:]
        print(f"  AUTO-MERGE CANDIDATE: keep={keep_id} merge={merge_ids}")

        if APPLY:
            for mid in merge_ids:
                merge_customers(keep_id=keep_id, merge_id=mid, verbose=True)
                merged_count += 1
        else:
            print("  (dry-run) set APPLY=True untuk eksekusi merge grup ini.")
    else:
        print("  SKIP auto-merge (overlap email tidak memenuhi threshold).")

print("\n=========================================")
print("DONE. APPLY=", APPLY, " merged_count=", merged_count)
print("=========================================")
