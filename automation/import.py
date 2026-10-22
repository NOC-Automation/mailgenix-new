# how to run : python import.py data.csv
import os
import django
import re
from datetime import datetime
from django.db import IntegrityError

# ========== CONFIG DJANGO ==========
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

# ========== IMPORT MODEL ==========
from core.models import SiteLocation, FloorLevel, Rack, Customers, ARGroup, AR, MailingList

# ========== PROGRESS BAR ==========
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except Exception:
    TQDM_AVAILABLE = False

def pbar(iterable=None, total=None, desc=None):
    if TQDM_AVAILABLE:
        return tqdm(iterable=iterable, total=total, desc=desc, ncols=100)
    return iterable if iterable is not None else range(total or 0)

# =====================================================
# HELPERS (robust parsing)
# =====================================================

AR_EMAIL_RE = re.compile(r"[\w\.\+\-]+@[\w\.\-]+", re.I)
PHONE_RE    = re.compile(r"\+?\d[\d\- ]{5,}\d")

HEADER = [
    'site_name','floor_name','rack_name','customer_name','authorized_string','office_phone',
    'ar1_name','ar1_email','ar1_mobile','ar2_name','ar2_email','ar2_mobile','ar3_name','ar3_email','ar3_mobile',
    'ml1','ml2','ml3','validity_AR','due_date'
]

def split_top_level(line: str):
    tokens, buf = [], []
    in_q, qch = False, ''
    depth_sq = depth_pa = 0
    for ch in line:
        if ch == '"':
            if in_q and qch == '"':
                in_q = False; qch = ''
            elif not in_q:
                in_q = True; qch = '"'
            buf.append(ch); continue
        if not in_q:
            if ch == '[':   depth_sq += 1
            elif ch == ']': depth_sq = max(0, depth_sq-1)
            elif ch == '(': depth_pa += 1
            elif ch == ')': depth_pa = max(0, depth_pa-1)
            if ch == ',' and depth_sq == 0 and depth_pa == 0:
                tokens.append(''.join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    tokens.append(''.join(buf).strip())
    return tokens

def parse_ar_combolist(s: str):
    out = []
    if not s: return out
    s = s.strip()
    if not (s.startswith('[') and s.endswith(']')):
        return out

    inner = s[1:-1].strip()
    items = []
    depth, start = 0, None
    in_q, qch = False, ''

    for i, ch in enumerate(inner):
        if ch == '"':
            if in_q and qch == '"':
                in_q = False; qch = ''
            elif not in_q:
                in_q = True; qch = '"'
        if not in_q:
            if ch == '(':
                if depth == 0: start = i+1
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and start is not None:
                    items.append(inner[start:i])
                    start = None

    for g in items:
        parts, b = [], []
        in_q, qch = False, ''
        for ch in g:
            if ch in ('"', "'"):
                if in_q and ch == qch:
                    in_q = False; qch = ''
                elif not in_q and (not b or b[-1] in (',', '(')):
                    in_q = True; qch = ch
                b.append(ch); continue
            if ch == ',' and not in_q:
                parts.append(''.join(b).strip().strip('"\''))
                b = []
            else:
                b.append(ch)
        parts.append(''.join(b).strip().strip('"\''))
        if len(parts) >= 4:
              parts = parts[1:]

        while len(parts) < 3:
            parts.append('')

        name, email, mobile = parts[:3]

        email = (email or '').strip().lstrip('+')

        if email and not AR_EMAIL_RE.fullmatch(email or ''):
            m = AR_EMAIL_RE.search(email)
            if m: email = m.group(0)
            else: email = ''

        if mobile and not PHONE_RE.fullmatch(mobile or ''):
            m = PHONE_RE.search(mobile or '')
            if m: mobile = m.group(0).replace(' ', '')

        if not email:
              continue

        out.append({
            'name':   name or None,
            'email': (email or '').lower() or None,
            'mobile': mobile or None,
        })
    return out

def normalize_validity(val):
    if not val: return None
    s = str(val).strip()
    sl = s.lower()
    if sl.startswith("valid"): return "Valid"
    if sl.startswith("exp"):   return "Expired"
    return s if s in ("Valid","Expired") else None

def parse_date(s):
    if not s: return None
    s = s.strip()
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%Y/%m/%d","%d-%b-%y","%d-%b-%Y","%d-%B-%y","%d-%B-%Y","%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except:
            pass
    return None

def unbox_single_quoted_list(s):
      if not s: return s
      t = s.strip()
      if t.startswith("[") and t.endswith("]"):
          inner = t[1:-1].strip()
          if (inner.startswith('"') and inner.endswith('"')) or (inner.startswith("'") and inner.endswith("'")):
              return inner[1:-1]
          # Handle unquoted single value like ["PT. LINK NET,TBK"]
          if '(' not in inner:
              return inner
      return s

# =====================================================
# CSV LOADER
# =====================================================

def load_rows_solution_c(filename):
    with open(filename, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]

    header = split_top_level(lines[0])
    if [h.strip() for h in header] != HEADER:
        header = HEADER[:]

    rows = []
    fixed = 0

    for ln in lines[1:]:
        toks = split_top_level(ln)
        row  = {h: (toks[i] if i < len(toks) else "") for i,h in enumerate(header)}
        row["_raw_tokens"] = toks[:]

        row["customer_name"] = unbox_single_quoted_list(row.get("customer_name",""))
        if row.get("rack_name","").startswith("DH01PT."):
            row["customer_name"] = "PT. Tuntun Sekuritas Indonesia"
            row["rack_name"]     = "DH01"
            fixed += 1

        # force last two tokens as validity/due if present
        if len(toks) >= 2:
            row["validity_AR"] = toks[-2].strip()
            row["due_date"]    = toks[-1].strip()

        # Parse AR
        contacts = []
        ar_raw = (row.get("ar1_name") or "").strip()
        if ar_raw.startswith("[") and ar_raw.endswith("]"):
            contacts = parse_ar_combolist(ar_raw)
        else:
            for p in ("ar1","ar2","ar3"):
                name   = (row.get(f"{p}_name")   or "").strip() or None
                email  = (row.get(f"{p}_email")  or "").strip().lower() or None
                mobile = (row.get(f"{p}_mobile") or "").strip() or None
                if email:
                    contacts.append({"name":name,"email":email,"mobile":mobile})

        contacts = [c for c in contacts if c.get("email")]
        row["_contacts"]     = contacts
        row["validity_AR"]   = normalize_validity(row.get("validity_AR"))
        row["_due_date_obj"] = parse_date(row.get("due_date"))

        rows.append(row)

    print(f"🔍 CSV parsed: {len(rows)} rows | fixed rows: {fixed}")
    return rows

# =====================================================
# IMPORT PIPELINE
# =====================================================

def import_csv(filename):
    rows = load_rows_solution_c(filename)
    if not rows:
        print("CSV kosong.")
        return

    print("📦 Preloading existing data...")
    sites     = {s.name: s for s in SiteLocation.objects.all()}
    floors    = {(f.site_location_id, f.name): f for f in FloorLevel.objects.all()}
    racks     = {(r.floor_level_id, r.name_racks): r for r in Rack.objects.all()}
    customers = {c.name_customer: c for c in Customers.objects.all()}

    # PASS 1 — Sites
    for r in pbar(rows, desc="Pass-1 Sites"):
        name = (r.get("site_name") or "").strip()
        if name and name not in sites:
            sites[name] = SiteLocation.objects.create(name=name)

    # PASS 2 — Floors
    for r in pbar(rows, desc="Pass-2 Floors"):
        s = sites.get((r.get("site_name") or "").strip())
        f = (r.get("floor_name") or "").strip()
        if s and f:
            key = (s.id, f)
            if key not in floors:
                floors[key] = FloorLevel.objects.create(site_location=s, name=f)

    # PASS 3 — Racks
    for r in pbar(rows, desc="Pass-3 Racks"):
        s = sites.get((r.get("site_name") or "").strip())
        f = floors.get((s.id, (r.get("floor_name") or "").strip())) if s else None
        if not f:
            continue

        rn_field   = (r.get("rack_name") or "").strip()
        rack_names = []

        if rn_field.startswith("[") and rn_field.endswith("]"):
            inner = rn_field[1:-1]
            tmp, b, in_q, qch = [], [], False, ""
            for ch in inner:
                if ch in ('"',"'"):
                    if in_q and ch == qch: in_q=False; qch=""
                    elif not in_q:         in_q=True;  qch=ch
                    b.append(ch); continue
                if ch == "," and not in_q:
                    tok = ''.join(b).strip().strip('"\'')
                    if tok: tmp.append(tok)
                    b = []
                else:
                    b.append(ch)
            tok = ''.join(b).strip().strip('"\'')
            if tok: tmp.append(tok)
            rack_names = [x for x in tmp if x]
        else:
            if rn_field:
                rack_names = [rn_field]

        for rn in rack_names:
            key = (f.id, rn)
            if key not in racks:
                racks[key] = Rack.objects.create(floor_level=f, name_racks=rn)

    # PASS 4 — Customers
    for r in pbar(rows, desc="Pass-4 Customers"):
        cname = (r.get("customer_name") or "").strip()
        if cname and cname not in customers:
            customers[cname] = Customers.objects.create(
                name_customer=cname,
                authorized=(r.get("authorized_string") or "").strip() or None,
                office_phone=(r.get("office_phone") or "").strip() or None
            )

    # PASS 5 — Customer↔Rack
    print("🔗 Applying Customer ↔ Rack relationships...")
    links = []
    for r in rows:
        cname = (r.get("customer_name") or "").strip()
        c = customers.get(cname)
        if not c: continue

        s = sites.get((r.get("site_name") or "").strip())
        f = floors.get((s.id, (r.get("floor_name") or "").strip())) if s else None

        rn_field   = (r.get("rack_name") or "").strip()
        rack_names = []

        if rn_field.startswith("[") and rn_field.endswith("]"):
            inner = rn_field[1:-1]
            tmp, b, in_q, qch = [], [], False, ""
            for ch in inner:
                if ch in ('"',"'"):
                    if in_q and ch == qch: in_q=False; qch=""
                    elif not in_q:         in_q=True;  qch=ch
                    b.append(ch); continue
                if ch == "," and not in_q:
                    tok = ''.join(b).strip().strip('"\'')
                    if tok: tmp.append(tok)
                    b = []
                else:
                    b.append(ch)
            tok = ''.join(b).strip().strip('"\'')
            if tok: tmp.append(tok)
            rack_names = [x for x in tmp if x]
        else:
            if rn_field:
                rack_names = [rn_field]

        for rn in rack_names:
            rk = racks.get((f.id, rn)) if f else None
            if rk:
                links.append((c.id, rk.id))

    if links:
        Customers.racks.through.objects.bulk_create(
            [Customers.racks.through(customers_id=cid, rack_id=rid) for cid, rid in links],
            ignore_conflicts=True
        )

    # PASS 6 — ARGroup (PASTIKAN MENGGANTI BAGIAN LAMA)
    argroups = {
        (ag.customer_id, ag.validity_AR, ag.due_date): ag
        for ag in ARGroup.objects.all()
    }
    created_ag = 0

    for r in pbar(rows, desc="Pass-6 ARGroup"):
        cname = (r.get("customer_name") or "").strip()
        c = customers.get(cname)
        if not c:
            continue

        validity = normalize_validity(r.get("validity_AR"))
        due = r.get("_due_date_obj")

        # jika tidak ada validity & due, skip
        if not (validity or due):
            continue

        key = (c.id, validity, due)

        # jika sudah ada dari preload atau dari iterasi sebelumnya
        if key in argroups:
            continue

        # ✔ get_or_create → aman untuk re-import
        try:
            ag_obj, created = ARGroup.objects.get_or_create(
                customer=c,
                validity_AR=validity,
                due_date=due,
            )
        except IntegrityError:
            # jika ada race / import paralel / benturan kecil
            ag_obj = ARGroup.objects.get(
                customer=c,
                validity_AR=validity,
                due_date=due,
            )
            created = False

        argroups[key] = ag_obj
        if created:
            created_ag += 1

    print(f"✔ ARGroup created: {created_ag}")

    # PASS 7 — AR & MAILING LIST
    created_ar, linked_ml = 0, 0
    ar_seen = set()

    for r in pbar(rows, desc="Pass-7 AR & MailingList"):
        cname = (r.get("customer_name") or "").strip()
        c = customers.get(cname)
        if not c: continue

        validity = normalize_validity(r.get("validity_AR"))
        due      = r.get("_due_date_obj")
        ag = argroups.get((c.id, validity, due))
        if not ag: continue

        contacts = r.get("_contacts") or []

        for info in contacts[:3]:
            email = (info.get("email") or "").strip().lower()
            if not email or (c.id, email) in ar_seen:
                continue

            ar_seen.add((c.id, email))

            ar_obj, created = AR.objects.get_or_create(
                customer=c,
                email_address=email,
                defaults={
                    "authorized_name": info.get("name") or None,
                    "mobile_phone":    info.get("mobile") or None,
                    "ar_group":        ag
                }
            )
            if created:
                created_ar += 1

            # ============================
            # MAILING LIST
            # ============================
            ml_candidates = []

            for key in ('ml1', 'ml2', 'ml3'):
                val = (r.get(key) or '').strip().strip('"').strip("'")
                if val and '@' in val:
                    ml_candidates.append(val)

            if not ml_candidates:
                toks = r.get('_raw_tokens') or []
                ar_end_index = None
                end_limit = max(0, len(toks) - 2)
                for i in range(end_limit - 1, -1, -1):
                    tok = toks[i].strip()
                    if tok.endswith(']') and not tok.startswith('[('):
                        ar_end_index = i
                        break
                if ar_end_index is not None:
                    ml_slice = toks[ar_end_index+1 : max(ar_end_index+1, len(toks)-2)]
                    ml_slice = ml_slice[:3]
                    for ml in ml_slice:
                        ml = ml.strip().strip('"').strip("'")
                        if '@' in ml and not ml.startswith('[('):
                            ml_candidates.append(ml)

            # Deduplicate & link
            ml_candidates = list(dict.fromkeys(ml_candidates))
            for ml_name in ml_candidates:
                ml_obj, _ = MailingList.objects.get_or_create(name=ml_name)
                ar_obj.mailing_lists.add(ml_obj)
                linked_ml += 1

    print(f"✔ AR created: {created_ar}")
    print(f"✔ AR↔ML links: {linked_ml}")
    print("🎉 IMPORT SELESAI")

# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("Robust CSV Importer (FINAL w/ minimal ML fallback)")
    parser.add_argument("csvfile")
    args = parser.parse_args()
    import_csv(args.csvfile)
