# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Q, Count
from django.template.loader import render_to_string
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.conf import settings
from email.message import EmailMessage as StdEmailMessage
from email.policy import SMTP

from datetime import date, datetime, timedelta
import logging
import json
import re
import uuid
import csv
import io
import calendar
from pathlib import Path

from .models import (
    EmailLogs, FloorLevel, MailingList,
    AR, ARGroup, Customers, Rack, SiteLocation, SupportGroup, ActivityLog, Changelog, MailingGroup,
    CustomerAdditionalMailingList, CustomerAssociation, SequenceCounter, SequenceRecord, SequenceAuditLog,
    ChecklistDefinition, ChecklistSubmission, ChecklistEvidence, RemoteHandsReport, RemoteHandsAttachment
)

# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------
User = get_user_model()

logger = logging.getLogger(__name__)


def _natural_floor_sort_key(value):
    """Natural ordering for labels such as Level 1, Level 2, Level 10."""
    text = str(value or "").strip()
    parts = re.split(r"(\d+)", text.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def _record_activity(*, user, action, entity_type="", entity_id="", entity_label="", description="", metadata=None, status="success"):
    """Best-effort append-only audit trail. Logging must never break the operational action."""
    try:
        ActivityLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            entity_type=entity_type or "",
            entity_id=str(entity_id or ""),
            entity_label=(entity_label or "")[:255],
            description=(description or "")[:500],
            metadata=metadata or {},
            status=status or "success",
        )
    except Exception as exc:
        logger.warning("[ActivityLog] unable to persist log: %s", exc, exc_info=True)


def _customer_validity_summary():
    """Return counts of customer validity badges used by the dashboard."""
    counts = {"active": 0, "expiring": 0, "expired": 0}
    for customer in Customers.objects.prefetch_related("ar_groups", "support_groups"):
        state = _customer_status(customer).get("label", "Active")
        if state == "Expired":
            counts["expired"] += 1
        elif state == "Expiring Soon":
            counts["expiring"] += 1
        else:
            counts["active"] += 1
    return counts


def _authorized_person_summary():
    """Deduplicated AR dashboard counts by customer + email, compatible with v1.7 data."""
    rank = {"expired": 0, "expiring": 1, "active": 2}
    best = {}
    for ar in AR.objects.select_related("ar_group").order_by("id"):
        key = (ar.customer_id, _normalize_email(ar.email_address) or f"id:{ar.id}")
        _, _, state = _effective_ar_validity(ar)
        current = best.get(key)
        if current is None or rank.get(state["key"], 0) > rank.get(current, 0):
            best[key] = state["key"]
    return {
        "total": len(best),
        "active": sum(1 for x in best.values() if x == "active"),
        "expiring": sum(1 for x in best.values() if x == "expiring"),
        "expired": sum(1 for x in best.values() if x == "expired"),
    }

NOTIFICATION_TEMPLATE_MAP = {
    "outage": "components/email/notification_v195.html",
    "preventive-maintenance": "components/email/notification_v195.html",
    "sharing-information": "components/email/notification_v195.html",
    "site-access": "components/email/notification_v195.html",
    "general-cleaning": "components/email/notification_v195.html",
    "response-alarm": "components/email/notification_v195.html",
}

# v1.9.5 template registry: 32 source-compatible template selections.
NOTIFICATION_TEMPLATE_REGISTRY = {
    "outage": {"label": "Outage", "subtypes": ["Outage Report"], "variants": ["General", "A100", "BOND"]},
    "preventive-maintenance": {"label": "Preventive Maintenance", "subtypes": ["Preventive Maintenance"], "variants": ["General", "A100", "BOND"]},
    "response-alarm": {"label": "Response Alarm", "subtypes": ["Response Alarm"], "variants": ["General", "A100"]},
    "general-cleaning": {"label": "General Cleaning", "subtypes": ["Schedule General Cleaning"], "variants": ["General", "A100", "BOND"]},
    "site-access": {"label": "Site Access", "subtypes": ["Site Access Information"], "variants": ["General", "A100", "BOND"]},
    "sharing-information": {"label": "Sharing Information", "subtypes": ["General", "Bomb", "Demonstration", "Earthquake", "Fire", "Flooding"], "variants": ["General", "A100", "BOND"]},
}



VARIANT_FOOTERS = {
    "general": {
        "email": "nttapac.id.noc@global.ntt",
        "phone": "+62 21-50930-115",
        "mobile": "+62 811-1908-0867",
    },
    "a100": {
        "email": "ap.id.myservicedesk@global.ntt",
        "phone": "+62 21-50930-116",
        "mobile": "+62 811-8816-916",
    },
    "bond": {
        "email": "ap.id.myservicedesk@global.ntt",
        "phone": "+62 21-50930-116",
        "mobile": "+62 815-9807-094",
    },
}

MONTH_NUMBER = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

def _variant_footer(variant):
    return VARIANT_FOOTERS.get(_norm(variant).lower(), VARIANT_FOOTERS["general"])

def _maintenance_earliest_date(value):
    """Best-effort natural schedule sort using the first day + month + year in display text.

    Supports examples such as:
    - 08 October 2026
    - 27 - 28 October 2026
    - 16 - 19 & 20 - 21 October 2026
    """
    text = _norm(value)
    if not text:
        return date.max
    match = re.search(
        r"(?P<day>\d{1,2}).*?(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<year>\d{4})",
        text,
        flags=re.I,
    )
    if not match:
        return date.max
    try:
        return date(
            int(match.group("year")),
            MONTH_NUMBER[match.group("month").lower()],
            int(match.group("day")),
        )
    except (ValueError, KeyError):
        return date.max

def _parse_maintenance_activities(raw):
    try:
        rows = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        rows = []
    cleaned = []
    if not isinstance(rows, list):
        return cleaned
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item = _norm(row.get("item"))
        frequency = _norm(row.get("frequency"))
        date_time = _norm(row.get("date_time"))
        mop_attached = str(row.get("mop_attached", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        if not any((item, frequency, date_time)):
            continue
        cleaned.append({
            "item": item or "-",
            "frequency": frequency or "-",
            "date_time": date_time or "-",
            "remarks": "MOP Attached" if mop_attached else "-",
            "_sort": _maintenance_earliest_date(date_time),
            "_index": idx,
        })
    cleaned.sort(key=lambda row: (row["_sort"], row["_index"]))
    for row in cleaned:
        row.pop("_sort", None)
        row.pop("_index", None)
    return cleaned

NOTIFICATION_GALLERY = [
    ("outage", "Outage", "Occurrence, status, recovery, and root-cause notification."),
    ("preventive-maintenance", "Preventive Maintenance", "Preventive or planned maintenance notification."),
    ("sharing-information", "Sharing Information", "General, bomb, demonstration, earthquake, fire, or flooding information."),
    ("site-access", "Site Access", "Site access information and approval notification."),
    ("general-cleaning", "General Cleaning", "Scheduled data-center cleaning notification."),
    ("response-alarm", "Response Alarm", "Alarm response and operational information notification."),
]


# Inline assets used when exporting Outlook-compatible .eml drafts.
# HTML previews keep their original relative paths; only the exported
# email body is rewritten to CID references.
EML_INLINE_ASSETS = {
    "./asset/ntt data logo email.png": {
        "cid": "mailgenix_ntt_logo",
        "path": Path(settings.BASE_DIR) / "frontend" / "templates" / "components" / "email" / "asset" / "ntt data logo email.png",
        "maintype": "image",
        "subtype": "png",
        "filename": "ntt-data-logo.png",
    },
}


def _prepare_eml_html_and_assets(html):
    """Rewrite known local image paths to CID URLs and return used assets."""
    html_for_eml = html
    used_assets = []

    for source, asset in EML_INLINE_ASSETS.items():
        if source not in html_for_eml:
            continue
        html_for_eml = html_for_eml.replace(source, f"cid:{asset['cid']}")
        used_assets.append(asset)

    return html_for_eml, used_assets


def _prepare_browser_preview_html(html):
    """Rewrite local email asset paths to URLs served by Django static files."""
    replacements = {
        "./asset/ntt data logo email.png": f"{settings.STATIC_URL}email/ntt-data-logo.png",
    }
    preview_html = html or ""
    for source, target in replacements.items():
        preview_html = preview_html.replace(source, target)
    return preview_html


def _attach_inline_assets(html_part, assets):
    """Attach images as multipart/related resources for Outlook .eml drafts."""
    for asset in assets:
        asset_path = Path(asset["path"])
        if not asset_path.is_file():
            raise FileNotFoundError(f"Inline email asset not found: {asset_path}")

        html_part.add_related(
            asset_path.read_bytes(),
            maintype=asset["maintype"],
            subtype=asset["subtype"],
            cid=f"<{asset['cid']}>",
            filename=asset["filename"],
            disposition="inline",
        )


# ---------------------------------------------------------------------
# AUTH / QUERY HELPERS
# ---------------------------------------------------------------------
def _is_admin(user):
    """Return True jika user terautentikasi dan berperan admin/superuser."""
    return (
        getattr(user, 'is_authenticated', False)
        and (
            getattr(user, 'role', None) == 'admin'
            or getattr(user, 'is_superuser', False)
        )
    )


def get_email_logs_for_component(user):
    """Ambil queryset EmailLogs untuk komponen UI; semua user bisa melihat logs."""
    qs = EmailLogs.objects.select_related('email_account', 'mailing_list', 'customer', 'user')
    return qs.order_by('-created_at')


# ---------------------------------------------------------------------
# LOGGING HELPERS
# ---------------------------------------------------------------------
def _format_tenant_log_body(action, details):
    """
    Ubah details menjadi body log yang singkat & informatif.
    Hanya tampilkan SATU perubahan utama, sesuai prioritas.
    """
    if not isinstance(details, dict):
        return ""

    # 1) Prioritas tertinggi: pindah rack
    rack_moved = details.get("rack_moved")
    if isinstance(rack_moved, dict):
        old_rack = rack_moved.get("from") or "-"
        new_rack = rack_moved.get("to") or "-"
        if old_rack != new_rack:
            return f"Moved rack: {old_rack} → {new_rack}"

    # 2) Prioritas kedua: AR dipindah / swap
    ar_reordered = details.get("ar_reordered")
    if isinstance(ar_reordered, list) and ar_reordered:
        return "AR moved: " + ", ".join(ar_reordered)

    # 3) Prioritas ketiga: customer name berubah
    cust_name = details.get("customer_name")
    if isinstance(cust_name, dict):
        old_name = cust_name.get("from") or "-"
        new_name = cust_name.get("to") or "-"
        if old_name != new_name:
            return f"Customer Name: {old_name} → {new_name}"

    # 4) Prioritas berikutnya: validity
    validity = details.get("validity")
    if isinstance(validity, dict):
        old_v = validity.get("from") or "-"
        new_v = validity.get("to") or "-"
        if old_v != new_v:
            return f"Validity: {old_v} → {new_v}"

    # 5) Prioritas berikutnya: date
    due_date = details.get("date")
    if isinstance(due_date, dict):
        old_d = due_date.get("from") or "-"
        new_d = due_date.get("to") or "-"
        if old_d != new_d:
            return f"Date: {old_d} → {new_d}"

    return ""


def _log_tenant_change(*, user, action, customer=None, customer_name=None, details=None):
    """
    Buat entry log ke EmailLogs agar tampil di Change Logs.

    - Untuk CREATE/UPDATE (customer masih ada): kirim customer=cust
    - Untuk DELETE customer: kirim customer=None dan customer_name="Nama Customer"
      agar log tidak ikut terhapus oleh CASCADE.
    """
    try:
        name = customer_name or (getattr(customer, "name_customer", None) if customer else None) or "-"
        subject = f"TENANT {action.upper()}: {name}"
        status = f"tenant-{action}"

        body = _format_tenant_log_body(action, details)

        EmailLogs.objects.create(
            subject=subject,
            status=status,
            body=body,
            customer=customer,
            user=user,
            sent_at=timezone.now(),
        )
        _record_activity(
            user=user,
            action="delete" if "delete" in action else ("create" if "create" in action else "update"),
            entity_type="Customer",
            entity_id=getattr(customer, "id", ""),
            entity_label=name,
            description=body or f"Tenant {action}: {name}",
            metadata={"tenant_action": action, **(details or {})},
        )
    except Exception as e:
        logger.error("[TenantLog] failed to write log: %s", e, exc_info=True)


# ---------------------------------------------------------------------
# NORMALIZATION / PARSING HELPERS
# ---------------------------------------------------------------------
def _norm(s):
        return (s or "").strip()


def _norm_customer_name(s: str) -> str:
    """
    Normalisasi nama customer agar konsisten dan mencegah duplikasi:
    - trim
    - NBSP -> space
    - collapse multiple spaces
    """
    s = (s or "").replace("\u00A0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_email(s: str) -> str:
    """Trim + lower sebuah email string; None → ''."""
    return (s or '').strip().lower()


def _safe_date_str(value):
    """Ubah objek date/datetime ke string ISO (YYYY-MM-DD); jika None/kasus lain, kembalikan ''."""
    if not value:
        return ''
    try:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        s = str(value)
        return s[:10]
    except Exception:
        return ''


def _parse_date(s):
    """Parse string 'YYYY-MM-DD' menjadi date; gagal → None."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


# ---------------------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------------------
def _validate_unique_authorized_emails(ars_payload):
    """
    Validator baru (lebih fleksibel):
    - Minimal 1 AR harus memiliki email.
    - AR yang email-nya terisi wajib memiliki format valid.
    - Email tidak boleh duplikat.
    - Jumlah AR dinamis/tidak dibatasi oleh aplikasi.
    """

    if not isinstance(ars_payload, list):
        return False, "Invalid AR payload"

    # Ambil AR yang memiliki email terisi
    filled = []
    for idx, item in enumerate(ars_payload, start=1):
        email = _normalize_email(item.get("email"))
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return False, f"Invalid email format for AR-{idx}"
            filled.append(email)

    # Minimal 1 AR dengan email
    if not filled:
        return False, "Minimal 1 AR harus memiliki email valid."

    # Email tidak boleh duplikat
    if len(filled) != len(set(filled)):
        return False, "Email AR tidak boleh duplikat."

    return True, None


# ---------------------------------------------------------------------
# ENTITY RESOLUTION HELPERS
# ---------------------------------------------------------------------
def _get_site(payload):
    # Minimal: pakai nama site dari payload (customer_site). (Kamu sudah kirim ini dari FE)
    site_name = _norm(payload.get("customer_site"))
    if not site_name:
        raise ValueError("Customer Site wajib dipilih.")
    site = SiteLocation.objects.filter(name__iexact=site_name).first()
    if not site:
        raise ValueError(f"Site '{site_name}' tidak ditemukan.")
    return site


def _resolve_or_create_floor(site, payload):
    # FE mengirim floor_level (id) dan floor_name (teks)
    floor_id = payload.get("floor_level") or payload.get("floor_id")
    floor_name = _norm(payload.get("floor_name"))

    if floor_id:
        fl = FloorLevel.objects.filter(id=floor_id, site_location=site).first()
        if not fl:
            raise ValueError("Floor Level tidak valid untuk Site yang dipilih.")
        return fl, False

    if not floor_name:
        raise ValueError("Floor Level wajib diisi.")

    try:
        with transaction.atomic():
            fl = FloorLevel.objects.filter(site_location=site, name__iexact=floor_name).first()
            if fl:
                return fl, False
            fl = FloorLevel.objects.create(site_location=site, name=floor_name)
            return fl, True
    except IntegrityError:
        fl = FloorLevel.objects.filter(site_location=site, name__iexact=floor_name).first()
        if fl:
            return fl, False
        raise


def _resolve_or_create_rack(floor, payload):
    rack_id = payload.get("rack_id")
    rack_name = _norm(payload.get("rack_name")) or _norm(payload.get("rack_location"))

    if rack_id:
        rk = Rack.objects.filter(id=rack_id, floor_level=floor).first()
        if not rk:
            raise ValueError("Rack tidak valid untuk Floor Level yang dipilih.")
        return rk, False

    if not rack_name:
        raise ValueError("Rack Location wajib diisi.")

    try:
        with transaction.atomic():
            rk = Rack.objects.filter(floor_level=floor, name_racks__iexact=rack_name).first()
            if rk:
                return rk, False
            rk = Rack.objects.create(floor_level=floor, name_racks=rack_name)
            return rk, True
    except IntegrityError:
        rk = Rack.objects.filter(floor_level=floor, name_racks__iexact=rack_name).first()
        if rk:
            return rk, False
        raise


def _pick_display_group(customer):
    """
    Pilih ARGroup 'display' untuk Customer agar Tenant List konsisten di semua rack.
    Strategi STABIL (tanpa field tambahan di DB): pilih group dengan id terkecil.
    - Stabil artinya tidak berubah hanya karena validity/due_date diubah.
    """
    return (
        ARGroup.objects
        .filter(customer=customer)
        .order_by("id")
        .first()
    )


# ---------------------------------------------------------------------
# MAILING LIST HELPERS
# ---------------------------------------------------------------------
def _collect_group_mailing_list(customer, grp):
    """
    Ambil daftar mailing list unik dari semua AR milik customer pada ARGroup tertentu.
    Return: list[str]
    """
    if not grp:
        return []

    ars_qs = (
        AR.objects
        .filter(customer=customer, ar_group=grp)
        .prefetch_related("mailing_lists")
        .order_by("id")
    )

    seen = set()
    ml_names = []
    for a in ars_qs:
        for ml in a.mailing_lists.all():
            name = (ml.name or "").strip()
            if name and name not in seen:
                seen.add(name)
                ml_names.append(name)

    return ml_names


def _normalize_mailing_list_values(raw_values):
    """
    Ubah payload mailing_list menjadi list string unik yang bersih.
    """
    vals = raw_values or []
    if isinstance(vals, str):
        vals = [v.strip() for v in vals.split(";")]

    cleaned = []
    seen = set()
    for v in vals:
        name = (str(v) or "").strip()
        if name and name not in seen:
            seen.add(name)
            cleaned.append(name)
    return cleaned


def _ensure_mailing_list_objects(raw_values):
    """
    Return list[MailingList] dari payload mailing_list.
    """
    names = _normalize_mailing_list_values(raw_values)
    objs = []
    for ml_name in names:
        obj, _ = MailingList.objects.get_or_create(name=ml_name)
        objs.append(obj)
    return objs


# ---------------------------------------------------------------------
# EMAIL TEMPLATE HELPERS
# ---------------------------------------------------------------------
def _notification_location(site):
    site = _norm(site).upper()
    mapping = {"JKT2": "NTT Global Data Centers – JKT 02", "JKT3": "NTT Global Data Centers – JKT 03"}
    return mapping.get(site, site or "[Put Site]")


def _notification_subject(category, data):
    site = _norm(data.get("site") or data.get("customer_site")) or "[Put Site]"
    ticket = _norm(data.get("ticket_number")) or "[Put No of Ticket]"
    update_type = _norm(data.get("update_type")) or "Occurrence"
    subject_type = {"Status Update": "Status", "Root Cause": "Cause"}.get(update_type, update_type)
    if category == "outage":
        return f"[{site}] [{ticket}] [Outage Report of {subject_type}] Notification NTT Data Center Service"
    if category == "preventive-maintenance":
        month_year = _norm(data.get("month_year"))
        if not month_year:
            source = _norm(data.get("maintenance_period")) or _norm(data.get("notification_date"))
            matches = re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", source, flags=re.I)
            if matches:
                month_year = f"{matches[0][0].title()} {matches[0][1]}"
        month_year = month_year or "<Month & Year>"
        return f"[{site}] [{ticket}] [Preventive Maintenance of {month_year}] Notification NTT Data Center Service"
    if category == "response-alarm":
        alarm_date = _norm(data.get("notification_date")) or "<Date-Month-Year>"
        return f"[{site}] - [{ticket}] [Response Alarm Information - {alarm_date}] Notification NTT Data Center Service"
    if category == "general-cleaning":
        customer = _norm(data.get("customer_name")) or "<Put Customer Name>"
        return f"[{site}] [{ticket}] [Schedule General Cleaning of Data Clean | {customer}] Notification NTT Data Center Service"
    if category == "site-access":
        level = _norm(data.get("floor_level")) or "PUT LEVEL"
        desc = _norm(data.get("description")) or "<Put Description>"
        approval = _norm(data.get("approval_status")) or "Need Approval/No Need Approval"
        return f"[{site}] [{level}] Site Access Information for {desc} -- {approval} #[{ticket}]"
    desc = _norm(data.get("description")) or _norm(data.get("subcategory")) or "<Put Description>"
    return f"[{site}] [{ticket}] [Sharing Information of {desc}] Notification NTT Data Center Service"


def _render_notification_html(*, type_notification, request=None, **kwargs):
    category = _norm(type_notification).lower()
    aliases = {
        "outage report notification": "outage", "maintenance notification": "preventive-maintenance",
        "sharing information notification": "sharing-information", "site access request": "site-access",
        "general cleaning notification": "general-cleaning", "response alarm notification": "response-alarm",
    }
    category = aliases.get(category, category)
    if category not in NOTIFICATION_TEMPLATE_MAP:
        return ""
    data = {k: _norm(v) for k, v in kwargs.items()}
    site = data.get("site") or data.get("customer_site") or "[Put Site]"
    ticket = data.get("ticket_number") or "[Put No of Ticket]"
    variant = data.get("variant") or "General"
    subcategory = data.get("subcategory") or NOTIFICATION_TEMPLATE_REGISTRY[category]["subtypes"][0]
    default_info = "If you have any questions or concerns regarding this notification, please contact our team through this email and attach the ticket number."
    additional = data.get("additional_information") or ""
    details=[]
    intro="Thank you for using NTT Global Data Centers Service."
    title=NOTIFICATION_TEMPLATE_REGISTRY[category]["label"] + " Notification"
    if category == "outage":
        title="Outage Report Notification"
        update=data.get("update_type") or "Occurrence"
        recovering=(data.get("fault_recovering_time") or "-") if update in {"Recovery","Root Cause"} else "-"
        root_cause=data.get("root_cause") or "Under Investigation"
        details=[
            ("Description of Incident", data.get("incident_description") or "-"),
            ("Fault Occurring Time", data.get("fault_occurring_time") or "-"),
            ("Fault Recovering Time", recovering),
            ("Service Impact", "Impact/No Impact to IT Load and Environment"),
            ("Current Action", data.get("current_action") or "-"),
            ("Root Cause", root_cause),
        ]
        intro += " We sincerely apologize for any inconvenience this may have caused you. We would like to inform you of Outage on Data Center service. Please find the details below."
        summary=[("Ticket Number", ticket),("Type",update),("Location",_notification_location(site))]
    elif category == "preventive-maintenance":
        title="Maintenance Notification"
        maintenance_activities = _parse_maintenance_activities(kwargs.get("maintenance_activities"))
        maintenance_period = data.get("maintenance_period") or data.get("notification_date") or "-"
        maintenance_status = data.get("maintenance_status") or "Assigned"
        maintenance_note = data.get("maintenance_note") or "-"
        summary=[
            ("Ticket Number",ticket),
            ("Title", "Preventive Maintenance"),
            ("Location",_notification_location(site)),
            ("Date & Time",maintenance_period),
            ("Status",maintenance_status),
        ]
        details=[]
        intro += " We would like to inform you for upcoming Maintenance activity within NTT Global Data Centers Indonesia. Please find the details for Maintenance as below."
    elif category == "response-alarm":
        title="Response Alarm Notification"
        summary=[("Ticket Number",ticket),("Title",data.get("description") or "Response Alarm"),("Location",_notification_location(site)),("Date",data.get("notification_date") or "-")]
        details=[("SOC Request Time",data.get("soc_request_time") or "-"),("Response Time",data.get("response_time") or "-"),("Data Hall",data.get("data_hall") or "-"),("Emergency Card",data.get("emergency_card") or "-"),("Status",data.get("status") or "-"),("Cause",data.get("root_cause") or "-")]
    elif category == "general-cleaning":
        title="General Cleaning Notification"
        summary=[("Ticket Number",ticket),("Title",data.get("description") or "Schedule General Cleaning"),("Location",_notification_location(site)),("Date & Time",data.get("notification_date") or "-")]
        details=[("Event Description",data.get("event_description") or "-"),("Location / Room",data.get("room") or "-"),("Status",data.get("status") or "-")]
    elif category == "site-access":
        title="Site Access Request"
        summary=[("Ticket Number",ticket),("Location",_notification_location(site)),("Level",data.get("floor_level") or "-")]
        details=[("Engineer Name/s",data.get("engineer_names") or "-"),("Day & Date",data.get("notification_date") or "-"),("Task Description",data.get("description") or "-"),("Time of Activity",data.get("activity_time") or "-"),("Room Name",data.get("room") or "-"),("Reason of Activity",data.get("reason") or "-"),("Tools",data.get("tools") or "-"),("Status",data.get("status") or "-"),("State of the Activity",data.get("activity_state") or "-")]
    else:
        title="Sharing Information Notification"
        summary=[("Ticket Number",ticket),("Information Type",subcategory),("Location",_notification_location(site)),("Date & Time",data.get("notification_date") or "-")]
        details=[("Event Description",data.get("description") or subcategory),("Service Impact",data.get("service_impact") or "-"),("Current Information",data.get("current_action") or "-")]
    footer = _variant_footer(variant)
    context={
        "category":category,"title":title,"variant":variant,"subcategory":subcategory,"intro":intro,
        "summary":summary,"details":details,"additional_information":additional,"default_information":default_info,
        "subject":_notification_subject(category,{**data,"site":site,"ticket_number":ticket,"subcategory":subcategory}),
        "site":site,"footer":footer,
        "maintenance_activities": locals().get("maintenance_activities", []),
        "maintenance_service_impact": "No Impact to IT Load",
        "maintenance_note": locals().get("maintenance_note", "-"),
    }
    return render_to_string(NOTIFICATION_TEMPLATE_MAP[category], context, request=request)


def _simple_html_to_text(html):
    """
    Fallback ringan text/plain untuk draft .eml.
    HTML tetap jadi body utama.
    """
    text = re.sub(r'<br\s*/?>', '\n', html or '', flags=re.I)
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------------------------------------------------------------
# USER MANAGEMENT HELPERS
# ---------------------------------------------------------------------
def _forbidden_json():
    return JsonResponse({'detail': 'Forbidden'}, status=403)


def _normalize_user_role(value):
    role = (value or 'user').strip().lower()
    return role if role in ('admin', 'user') else 'user'


def _apply_user_role_flags(user_obj, role):
    """
    Sinkronkan field role dengan flags Django.
    """
    user_obj.role = role
    user_obj.is_staff = (role == 'admin')
    user_obj.is_superuser = (role == 'admin')


def _serialize_user(user_obj):
    return {
        'id': user_obj.id,
        'username': user_obj.username,
        'role': getattr(user_obj, 'role', 'user'),
        'is_active': user_obj.is_active,
        'is_staff': user_obj.is_staff,
        'is_superuser': user_obj.is_superuser,
        'last_login': _safe_date_str(user_obj.last_login),
    }


# ---------------------------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------------------------
@login_required
def users_page(request):
    if not _is_admin(request.user):
        return redirect('home')

    context = {
        'active_menu': 'users',
        'is_admin': True,
    }
    return render(request, 'components/users_management.html', context)


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def users_api(request):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    if request.method == "GET":
        qs = User.objects.all().order_by('id')
        data = [_serialize_user(u) for u in qs]
        return JsonResponse({'results': data})

    # POST (Create)
    payload, error_response = _parse_json_request(request)
    if error_response:
        return error_response

    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    role = _normalize_user_role(payload.get('role'))
    is_active = bool(payload.get('is_active', True))

    if not username or not password:
        return JsonResponse({'detail': 'username dan password wajib diisi'}, status=400)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                role=role
            )
            _apply_user_role_flags(user, role)
            user.is_active = is_active
            user.save()

        _record_activity(user=request.user, action='create', entity_type='User', entity_id=user.id, entity_label=user.username, description=f'Created user {user.username}', metadata={'role': user.role, 'is_active': user.is_active})
        return JsonResponse({'status': 'created', 'id': user.id}, status=201)

    except IntegrityError:
        return JsonResponse({'detail': 'Username sudah dipakai'}, status=409)
    except Exception as e:
        logger.error("[UsersAPI] create failed: %s", e, exc_info=True)
        return JsonResponse({'detail': str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "PATCH", "DELETE"])
@csrf_protect
def user_detail_api(request, user_id):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    user = get_object_or_404(User, id=user_id)

    if request.method == "DELETE":
        if user.id == request.user.id:
            return JsonResponse({'detail': 'Tidak boleh menghapus akun sendiri.'}, status=400)

        deleted_username = user.username
        user.delete()
        _record_activity(user=request.user, action='delete', entity_type='User', entity_id=user_id, entity_label=deleted_username, description=f'Deleted user {deleted_username}')
        return JsonResponse({'status': 'deleted'})

    # PUT / PATCH (Update)
    payload, error_response = _parse_json_request(request)
    if error_response:
        return error_response

    username = payload.get('username')
    password = payload.get('password')
    role = payload.get('role')
    is_active = payload.get('is_active')

    if username is not None:
        username = (username or '').strip()
        if not username:
            return JsonResponse({'detail': 'Username tidak boleh kosong.'}, status=400)
        user.username = username

    if password:
        user.set_password(password)

    if role is not None:
        normalized_role = _normalize_user_role(role)
        _apply_user_role_flags(user, normalized_role)

    if is_active is not None:
        user.is_active = bool(is_active)

    try:
        with transaction.atomic():
            user.save()

        _record_activity(user=request.user, action='update', entity_type='User', entity_id=user.id, entity_label=user.username, description=f'Updated user {user.username}', metadata={'role': user.role, 'is_active': user.is_active})
        return JsonResponse({'status': 'updated'})

    except IntegrityError:
        return JsonResponse({'detail': 'Username mungkin sudah dipakai.'}, status=409)
    except Exception as e:
        logger.error("[UserDetailAPI] update failed: %s", e, exc_info=True)
        return JsonResponse({'detail': str(e)}, status=500)


# ---------------------------------------------------------------------
# HOME PAGE HELPERS
# ---------------------------------------------------------------------
def _get_home_dropdown_data():
    """
    Data dropdown dasar untuk dashboard / form UI.
    """
    floor_levels = list(FloorLevel.objects.select_related("site_location").all())
    floor_levels.sort(key=lambda f: (f.site_location.name.lower(), _natural_floor_sort_key(f.name)))
    return {
        "floor_levels": floor_levels,
        "site_locations": SiteLocation.objects.all(),
        "mailing_lists": MailingList.objects.all(),
    }


def _get_home_customer_data():
    """
    Data customer + AR + rack untuk komponen frontend di dashboard.
    """
    ars = (
        AR.objects
        .select_related("customer")
        .prefetch_related(
            "customer",
            "customer__racks__floor_level__site_location",
            "mailing_lists",
        )
        .all()
    )

    customers_with_racks = (
        Customers.objects
        .prefetch_related(
            "racks__floor_level__site_location",
            "ars__ar_group",
            "ars__mailing_lists",
        )
        .all()
    )

    return {
        "ars": ars,
        "customers_with_racks": customers_with_racks,
    }


def _get_home_logs_page(user, request, per_page=10):
    """
    Ambil page changelog untuk dashboard.
    """
    logs_qs = get_email_logs_for_component(user)
    paginator = Paginator(logs_qs, per_page)
    page_number = request.GET.get("page")
    return paginator.get_page(page_number)


def _get_floor_levels_distinct():
    """
    Data distinct floor levels untuk kebutuhan filter frontend.
    """
    return list(
        FloorLevel.objects
        .select_related("site_location")
        .values("name", "site_location__name")
        .distinct()
    )


def _handle_home_post_feedback(request):
    """
    Handler kecil untuk form POST sederhana di dashboard.
    Return redirect response.
    """
    floor_level = request.POST.get("floor_level")
    customer_name = request.POST.get("customer_name")

    if not floor_level:
        messages.error(request, "Floor level harus dipilih.")
    else:
        messages.success(
            request,
            f"Form berhasil dikirim! Floor: {floor_level}, Customer: {customer_name}"
        )

    return redirect("home")


# ---------------------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------------------
@login_required
def home(request):
    """
    Render dashboard utama:
    - Menyediakan data dropdown (site locations, floor levels, mailing lists).
    - Menyediakan data customer/rack/AR untuk komponen frontend.
    - Menampilkan changelog ter-paginasi.
    - Menangani POST sederhana untuk feedback form.
    """
    user = request.user
    is_admin = _is_admin(user)

    if request.method == "POST":
        return _handle_home_post_feedback(request)

    dropdown_data = _get_home_dropdown_data()
    customer_data = _get_home_customer_data()
    page_obj = _get_home_logs_page(user, request, per_page=10)
    floor_levels_distinct = _get_floor_levels_distinct()

    customer_validity = _customer_validity_summary()
    authorized_validity = _authorized_person_summary()
    # v1.9.7 dashboard validity: Authorized Person + Support Group + Contractor/WAF + Visitor/AVE.
    validity_active = authorized_validity["active"]
    validity_expiring = authorized_validity["expiring"]
    validity_expired = authorized_validity["expired"]
    today = timezone.localdate()
    for sg in SupportGroup.objects.all():
        if sg.validity_date and sg.validity_date < today:
            validity_expired += 1
        elif sg.validity_date and (sg.validity_date - today).days <= 30:
            validity_expiring += 1
        else:
            validity_active += 1
    for assoc in CustomerAssociation.objects.all():
        if assoc.validity_status == "Expired": validity_expired += 1
        elif assoc.validity_status == "Expiring Soon": validity_expiring += 1
        else: validity_active += 1
    validity_total = validity_active + validity_expiring + validity_expired
    validity_active_pct = round((validity_active / validity_total * 100) if validity_total else 0)
    tenant_jkt2_count = Customers.objects.filter(racks__floor_level__site_location__name__iexact="JKT2").distinct().count()
    tenant_jkt3_count = Customers.objects.filter(racks__floor_level__site_location__name__iexact="JKT3").distinct().count()
    tenant_max = max(tenant_jkt2_count, tenant_jkt3_count, 1)
    recent_activity = ActivityLog.objects.select_related("user").all()[:6]
    activity_page = Paginator(ActivityLog.objects.select_related("user").all(), 15).get_page(request.GET.get("activity_page"))
    changelog_entries = Changelog.objects.filter(is_published=True)[:8]

    context = {
        "active_menu": "dashboard",
        "is_admin": is_admin,
        "customer_count": Customers.objects.count(),
        "authorized_person_count": authorized_validity["total"],
        "rack_count": Rack.objects.count(),
        "support_group_count": SupportGroup.objects.count(),
        "support_group_active_count": SupportGroup.objects.filter(status=SupportGroup.STATUS_ACTIVE).count(),
        "support_group_expired_count": SupportGroup.objects.filter(status=SupportGroup.STATUS_EXPIRED).count(),
        "support_group_today_count": SupportGroup.objects.filter(created_at__date=timezone.localdate()).count(),
        "customer_active_count": customer_validity["active"],
        "customer_expiring_count": customer_validity["expiring"],
        "customer_expired_count": customer_validity["expired"],
        "authorized_active_count": authorized_validity["active"],
        "authorized_expiring_count": authorized_validity["expiring"],
        "authorized_expired_count": authorized_validity["expired"],
        "dashboard_validity_active": validity_active,
        "dashboard_validity_expiring": validity_expiring,
        "dashboard_validity_expired": validity_expired,
        "dashboard_validity_total": validity_total,
        "dashboard_validity_active_pct": validity_active_pct,
        "tenant_jkt2_count": tenant_jkt2_count,
        "tenant_jkt3_count": tenant_jkt3_count,
        "tenant_jkt2_pct": round(tenant_jkt2_count / tenant_max * 100),
        "tenant_jkt3_pct": round(tenant_jkt3_count / tenant_max * 100),
        "recent_activity": recent_activity,
        "activity_page": activity_page,
        "changelog_entries": changelog_entries,
        "notification_gallery": NOTIFICATION_GALLERY,
        "mailing_groupings": MailingGroup.objects.filter(is_active=True).select_related("site").prefetch_related("floors").order_by("site__name", "name"),
        "mailing_groups_all": MailingGroup.objects.select_related("site").prefetch_related("floors").order_by("site__name", "name"),
        "logs": page_obj.object_list,
        "page_obj": page_obj,
        "floor_levels_distinct": floor_levels_distinct,
        **dropdown_data,
        **customer_data,
    }

    return render(request, "home.html", context)


# ---------------------------------------------------------------------
# LOG EMAIL HELPERS
# ---------------------------------------------------------------------
def _resolve_customer_for_log(customer_id_raw=None, customer_name=None):
    """
    Resolve customer dari customer_id atau customer_name.
    """
    customer = None

    if customer_id_raw:
        try:
            customer = Customers.objects.filter(id=int(customer_id_raw)).first()
        except Exception:
            customer = None

    if not customer and customer_name:
        normalized_name = _norm_customer_name(customer_name)
        customer = Customers.objects.filter(name_customer__iexact=normalized_name).first()

    return customer


def _resolve_mailing_list_from_raw(mailing_list_id_raw):
    """
    Resolve MailingList object dari raw value mailing_list_id.
    Support string yang mungkin berisi angka campuran.
    """
    if not mailing_list_id_raw:
        return None

    ids = [int(x) for x in re.findall(r'\d+', str(mailing_list_id_raw))]
    if not ids:
        return None

    return MailingList.objects.filter(id=ids[0]).first()


def _resolve_email_account_for_customer_ml(customer, mailing_list_obj=None):
    """
    Ambil AR representative untuk customer.
    Jika mailing list tersedia, prioritaskan AR yang terhubung ke ML tersebut.
    """
    if not customer:
        return None

    if mailing_list_obj:
        ar = (
            AR.objects.select_related('customer')
            .filter(customer=customer, mailing_lists=mailing_list_obj)
            .first()
        )
        if ar:
            return ar

    return AR.objects.filter(customer=customer).first()


def _create_email_log(*, user, subject, body, status='queued', customer=None, mailing_list=None, email_account=None, sent_at=None):
    """
    Wrapper kecil untuk membuat EmailLogs agar tidak duplikatif.
    """
    return EmailLogs.objects.create(
        email_account=email_account,
        mailing_list=mailing_list,
        customer=customer,
        user=user,
        subject=subject,
        body=body,
        status=status,
        sent_at=sent_at,
    )


def _get_bulk_log_queryset(customer_site=None, floor_level=None):
    """
    Query AR untuk kebutuhan bulk logging.
    Mendukung:
    - bulk by site
    - bulk by floor
    """
    qs = (
        AR.objects
        .select_related('customer')
        .prefetch_related('mailing_lists', 'customer__racks__floor_level__site_location')
        .filter(customer__racks__floor_level__site_location__name=customer_site)
        .distinct()
    )

    if floor_level:
        qs = qs.filter(customer__racks__floor_level__name=floor_level)

    return qs


def _count_bulk_targets(ar_queryset):
    """
    Hitung jumlah target bulk secara kasar.
    Jika AR punya mailing list, hitung jumlah ML.
    Jika tidak, hitung 1.
    """
    recipient_count = 0

    for ar in ar_queryset:
        mls = list(ar.mailing_lists.all())
        recipient_count += (len(mls) or 1)

    return recipient_count


# ---------------------------------------------------------------------
# LOG EMAIL
# ---------------------------------------------------------------------
@login_required
@require_POST
@csrf_protect
def log_email_send(request):
    """
    Logging aktivitas pengiriman email dari page Mailing List.

    Mode:
    1) Specific + Mailing List
    2) Specific tanpa Mailing List
    3) Bulk by site
    4) Bulk by floor
    """
    floor_level = request.POST.get('floor_level')
    customer_site = request.POST.get('customer_site')
    customer_id_raw = request.POST.get('customer_id')
    customer_name = request.POST.get('customer_name')
    mailing_list_id_raw = request.POST.get('mailing_list_id')
    subject = request.POST.get('subject', 'Email Notification')
    body = request.POST.get('body', '')

    customer = _resolve_customer_for_log(
        customer_id_raw=customer_id_raw,
        customer_name=customer_name,
    )

    mailing_list_obj = _resolve_mailing_list_from_raw(mailing_list_id_raw)

    # ---------------- Specific + ML ----------------
    if mailing_list_obj:
        if not customer:
            _create_email_log(
                user=request.user,
                subject=subject,
                body=body,
                status='queued',
                customer=None,
                mailing_list=None,
                email_account=None,
                sent_at=None,
            )
            return JsonResponse({'status': 'success', 'mode': 'specific', 'count': 1})

        email_account = _resolve_email_account_for_customer_ml(customer, mailing_list_obj)

        _create_email_log(
            user=request.user,
            subject=subject,
            body=body,
            status='queued',
            customer=customer,
            mailing_list=mailing_list_obj,
            email_account=email_account,
            sent_at=None,
        )
        return JsonResponse({'status': 'success', 'mode': 'specific', 'count': 1})

    # ---------------- Specific tanpa ML ----------------
    if customer:
        email_account = _resolve_email_account_for_customer_ml(customer, mailing_list_obj=None)

        _create_email_log(
            user=request.user,
            subject=subject,
            body=body,
            status='queued',
            customer=customer,
            mailing_list=None,
            email_account=email_account,
            sent_at=None,
        )
        return JsonResponse({'status': 'success', 'mode': 'specific-no-ml', 'count': 1})

    # ---------------- Bulk by Site / Floor ----------------
    if not customer_site:
        return JsonResponse(
            {'status': 'error', 'message': 'Customer site is required for bulk'},
            status=400
        )

    bulk_qs = _get_bulk_log_queryset(
        customer_site=customer_site,
        floor_level=floor_level,
    )

    recipient_count = _count_bulk_targets(bulk_qs)

    # Optional: status tetap stabil, count ditaruh di body
    status = 'bulk-queued'
    bulk_body = body
    if recipient_count:
        bulk_body = f"{body}\n\n[Bulk targets: {recipient_count}]".strip()

    _create_email_log(
        user=request.user,
        subject=subject,
        body=bulk_body,
        status=status,
        customer=None,
        mailing_list=None,
        email_account=None,
        sent_at=None,
    )

    return JsonResponse({
        'status': 'success',
        'mode': 'bulk-site' if not floor_level else 'bulk-floor',
        'count': 1,
        'targets': recipient_count,
    })


# ---------------------------------------------------------------------
# TENANT LIST HELPERS
# ---------------------------------------------------------------------
def _parse_positive_int(raw_value, default):
    try:
        value = int(raw_value)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _build_tenant_search_blob(site_name, customer_name, rack_name, authorized_persons, emails, phones, validities, dates):
    return " ".join([
        site_name or "",
        customer_name or "",
        rack_name or "",
        " ".join(authorized_persons or []),
        " ".join(emails or []),
        " ".join(phones or []),
        " ".join(validities or []),
        " ".join(dates or []),
    ]).lower()


def _score_tenant_row(tokens, site_name, customer_name, rack_name):
    if not tokens:
        return 0

    first = tokens[0]
    score = 0

    if (site_name or "").lower().startswith(first):
        score += 3
    if (customer_name or "").lower().startswith(first):
        score += 3

    base_blob = " ".join([
        site_name or "",
        customer_name or "",
        rack_name or "",
    ]).lower()

    score += sum(1 for token in tokens if token and token in base_blob)
    return score



CSV_CUSTOMER_HEADERS = [
    "customer_name", "customer_site", "floor_level", "rack_location",
    "validity", "due_date",
    "authorized_name", "authorized_email", "authorized_phone",
]
CSV_CUSTOMER_OPTIONAL_HEADERS = ["additional_mailing_list"]


def _csv_boolish_text(value):
    return _norm(value).replace("\ufeff", "")


def _csv_import_one_customer_row(row, user):
    """Import one row as a customer location plus a customer-wide Authorized Person.

    Repeating the same customer/email across multiple rack rows creates one AR and many
    customer rack locations. Validity accepts Valid/Expired plus display aliases
    Active/Expiring Soon for operator-friendly CSVs.
    """
    name = _norm_customer_name(row.get("customer_name"))
    site_name = _norm(row.get("customer_site"))
    floor_name = _norm(row.get("floor_level"))
    rack_name = _norm(row.get("rack_location"))
    validity_raw = _norm(row.get("validity")) or ARGroup.VALIDITY_VALID
    validity_map = {
        "valid": ARGroup.VALIDITY_VALID,
        "active": ARGroup.VALIDITY_VALID,
        "expiring soon": ARGroup.VALIDITY_VALID,
        "expired": ARGroup.VALIDITY_EXPIRED,
    }
    validity = validity_map.get(validity_raw.lower())
    due_date_raw = _norm(row.get("due_date"))
    due_date = _parse_date(due_date_raw)
    auth_name = _norm(row.get("authorized_name"))
    email = _normalize_email(row.get("authorized_email"))
    phone = _norm(row.get("authorized_phone"))
    additional_mailing_raw = _norm(row.get("additional_mailing_list") or row.get("mailing_list"))

    if not name: raise ValueError("customer_name wajib diisi")
    if not site_name: raise ValueError("customer_site wajib diisi")
    if not floor_name: raise ValueError("floor_level wajib diisi")
    if not rack_name: raise ValueError("rack_location wajib diisi")
    if not validity:
        raise ValueError("validity harus Valid, Active, Expiring Soon, atau Expired")
    if due_date_raw and due_date is None:
        raise ValueError("due_date harus berformat YYYY-MM-DD")
    has_ar_data = bool(email or auth_name or phone)
    if has_ar_data and not email:
        raise ValueError("authorized_email wajib diisi jika data Authorized Person diisi")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("authorized_email tidak valid")

    # Date is authoritative for stored validity.
    validity = _profile_ar_status_value(due_date) if validity != ARGroup.VALIDITY_EXPIRED else ARGroup.VALIDITY_EXPIRED

    cust = Customers.objects.filter(name_customer__iexact=name).first()
    customer_created = False
    if not cust:
        cust = Customers.objects.create(name_customer=name, created_by=user)
        customer_created = True

    site, _ = SiteLocation.objects.get_or_create(name=site_name)
    floor = FloorLevel.objects.filter(site_location=site, name__iexact=floor_name).first()
    if not floor:
        floor = FloorLevel.objects.create(site_location=site, name=floor_name)
    rack = Rack.objects.filter(floor_level=floor, name_racks__iexact=rack_name).first()
    if not rack:
        rack = Rack.objects.create(floor_level=floor, name_racks=rack_name)
    cust.racks.add(rack)

    grp = ARGroup.objects.filter(customer=cust, rack__isnull=True).order_by("id").first()
    ar = None
    ar_created = False
    if email:
        if not grp:
            grp = ARGroup.objects.create(customer=cust, rack=None, validity_AR=ARGroup.VALIDITY_VALID, due_date=None)
        ar = AR.objects.filter(customer=cust, ar_group=grp, email_address__iexact=email).first()
        if not ar:
            ar = AR.objects.create(
                customer=cust, ar_group=grp, email_address=email,
                authorized_name=auth_name, mobile_phone=phone,
                validity=validity, due_date=due_date,
            )
            ar_created = True
        else:
            ar.authorized_name = auth_name
            ar.mobile_phone = phone
            # When an AR is repeated only to add another rack, do not create another AR.
            if due_date is not None:
                ar.due_date = due_date
                ar.validity = validity
            ar.save(update_fields=["authorized_name", "mobile_phone", "due_date", "validity", "updated_at"])
    if additional_mailing_raw:
        for email_value in _parse_additional_mailing_list_values(additional_mailing_raw):
            CustomerAdditionalMailingList.objects.get_or_create(customer=cust, email_address=email_value)

    return {
        "customer_id": cust.id,
        "customer_created": customer_created,
        "rack_id": rack.id,
        "group_id": grp.id if grp else None,
        "ar_id": ar.id if ar else None,
        "ar_created": ar_created,
    }


@login_required
@require_http_methods(["GET"])
def customers_csv_template(request):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=CSV_CUSTOMER_HEADERS + CSV_CUSTOMER_OPTIONAL_HEADERS)
    writer.writeheader()
    base = {
        "customer_name": "PT Example Customer", "customer_site": "JKT3",
        "floor_level": "Level 1", "rack_location": "RACK-A01",
        "validity": "Valid", "due_date": "2026-12-31",
    }
    writer.writerow({**base, "authorized_name": "Andi Example", "authorized_email": "andi@example.com", "authorized_phone": "081234567890", "additional_mailing_list": "ops@example.com; management@example.com"})
    writer.writerow({**base, "authorized_name": "Budi Example", "authorized_email": "budi@example.com", "authorized_phone": "081234567891"})
    writer.writerow({**base, "authorized_name": "Citra Example", "authorized_email": "citra@example.com", "authorized_phone": "081234567892"})
    writer.writerow({**base, "authorized_name": "Dedi Example", "authorized_email": "dedi@example.com", "authorized_phone": "081234567893"})
    response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="mailgenix_customer_authorized_person_import_template.csv"'
    return response


@login_required
@require_http_methods(["POST"])
@csrf_protect
def customers_csv_import(request):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"detail": "Pilih file CSV terlebih dahulu."}, status=400)
    if not upload.name.lower().endswith(".csv"):
        return JsonResponse({"detail": "File harus berformat .csv"}, status=400)
    if upload.size > 5 * 1024 * 1024:
        return JsonResponse({"detail": "Ukuran CSV maksimal 5 MB."}, status=400)

    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return JsonResponse({"detail": "CSV harus menggunakan encoding UTF-8."}, status=400)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return JsonResponse({"detail": "CSV tidak memiliki header."}, status=400)

    normalized_headers = [(_csv_boolish_text(h)).lower() for h in reader.fieldnames]
    missing = [h for h in CSV_CUSTOMER_HEADERS if h not in normalized_headers]
    if missing:
        return JsonResponse({
            "detail": "Header CSV tidak lengkap.",
            "missing_headers": missing,
        }, status=400)

    # Map original column names to normalized keys so BOM/casing does not matter.
    header_map = {orig: (_csv_boolish_text(orig)).lower() for orig in reader.fieldnames}

    success = []
    errors = []
    seen_rows = 0

    for line_no, raw_row in enumerate(reader, start=2):
        row = {header_map.get(k, k): (v or "") for k, v in raw_row.items()}
        if not any(_norm(v) for v in row.values()):
            continue
        seen_rows += 1
        try:
            with transaction.atomic():
                result = _csv_import_one_customer_row(row, request.user)
            success.append({
                "line": line_no,
                "customer_name": _norm_customer_name(row.get("customer_name")),
                **result,
            })
        except (ValueError, ValidationError, IntegrityError) as exc:
            errors.append({
                "line": line_no,
                "customer_name": _norm_customer_name(row.get("customer_name")),
                "error": str(exc),
            })
        except Exception as exc:
            logger.error("[CSV Import] line %s failed: %s", line_no, exc, exc_info=True)
            errors.append({
                "line": line_no,
                "customer_name": _norm_customer_name(row.get("customer_name")),
                "error": "Internal error while importing this row.",
            })

    _record_activity(
        user=request.user, action="import", entity_type="Customer CSV", entity_label=upload.name,
        description=f"Imported tenant data via CSV: {len(success)} success, {len(errors)} failed",
        metadata={"filename": upload.name, "rows_read": seen_rows, "success_count": len(success), "error_count": len(errors)},
        status="success" if not errors else "partial",
    )

    return JsonResponse({
        "status": "completed",
        "rows_read": seen_rows,
        "success_count": len(success),
        "error_count": len(errors),
        "success": success,
        "errors": errors,
    })

# ---------------------------------------------------------------------
# TENANTS LIST (MAIN API)
# ---------------------------------------------------------------------
@login_required
@require_http_methods(["GET"])
def tenants_list_api(request):
    """Tenant list as Customer x Rack with ARs scoped to that rack/location."""
    page = _parse_positive_int(request.GET.get("page"), 1)
    per_page = min(_parse_positive_int(request.GET.get("per_page"), 10), 100)

    q = (request.GET.get("search") or "").strip().lower()
    tokens = [t for t in q.split() if t]

    ars_prefetch = Prefetch(
        "ars", queryset=AR.objects.select_related("ar_group__rack").order_by("id")
    )
    racks_prefetch = Prefetch(
        "racks", queryset=Rack.objects.select_related("floor_level__site_location").order_by("id")
    )
    groups_prefetch = Prefetch(
        "ar_groups", queryset=ARGroup.objects.select_related("rack").order_by("id")
    )

    customers = Customers.objects.prefetch_related(
        ars_prefetch, racks_prefetch, groups_prefetch
    ).all()

    rows = []
    for cust in customers:
        all_ars = list(cust.ars.all())
        all_groups = list(cust.ar_groups.all())
        racks = list(cust.racks.all())
        if not racks:
            continue

        for rk in racks:
            display_grp = next((g for g in all_groups if g.rack_id == rk.id), None)
            if display_grp is None:
                # Backward-compatible legacy group without rack relation.
                display_grp = next((g for g in all_groups if g.rack_id is None), None)

            if display_grp:
                ars_qs = [a for a in all_ars if a.ar_group_id == display_grp.id]
            else:
                ars_qs = []

            authorized_persons = [a.authorized_name or "" for a in ars_qs]
            emails = [a.email_address or "" for a in ars_qs]
            phones = [a.mobile_phone or "" for a in ars_qs]
            id_list = [a.id for a in ars_qs]

            due_date_val = (
                display_grp.due_date.isoformat()
                if display_grp and display_grp.due_date else ""
            )
            validity_val = (display_grp.validity_AR or "Valid") if display_grp else "Valid"
            dates = [due_date_val for _ in ars_qs] if ars_qs else []
            validities = [validity_val for _ in ars_qs] if ars_qs else []

            site_name = rk.floor_level.site_location.name if rk.floor_level else ""
            rack_loc_display = rk.name_racks or ""
            full_text = _build_tenant_search_blob(
                site_name=site_name, customer_name=cust.name_customer,
                rack_name=rack_loc_display, authorized_persons=authorized_persons,
                emails=emails, phones=phones, validities=validities, dates=dates,
            )
            if tokens and not all(tok in full_text for tok in tokens):
                continue

            score = _score_tenant_row(
                tokens=tokens, site_name=site_name,
                customer_name=cust.name_customer, rack_name=rack_loc_display,
            )
            rows.append({
                "site_location": site_name,
                "floor_level": rk.floor_level.name if rk.floor_level else "",
                "customer_id": cust.id,
                "customer_name": cust.name_customer,
                "rack_location": rack_loc_display,
                "rack_id": rk.id,
                "authorized_person_list": authorized_persons,
                "email_list": emails,
                "phone_list": phones,
                "date_list": dates,
                "validity_list": validities,
                "id_list": id_list,
                "group_id": display_grp.id if display_grp else None,
                "_score": score,
            })

    rows.sort(key=lambda r: (
        -int(r.get("_score", 0)),
        (r.get("customer_name") or "").lower(),
        (r.get("rack_location") or "").lower(),
    ))
    total = len(rows)
    start = (page - 1) * per_page
    sliced = rows[start:start + per_page]
    return JsonResponse({"results": sliced, "total": total})


# ---------------------------------------------------------------------
# TENANT DETAIL (LEGACY SINGLE-AR)
# ---------------------------------------------------------------------
@login_required
@require_http_methods(["PUT", "PATCH", "DELETE"])
@csrf_protect
def tenant_detail_api(request, tenant_id):
    """Endpoint legacy yang sudah ditiadakan; mengembalikan 410 (Gone)."""
    return JsonResponse({"detail": "Legacy API removed. Use group API."}, status=410)


# ---------------------------------------------------------------------
# TENANTS BY CUSTOMER HELPERS
# ---------------------------------------------------------------------
def _parse_json_request(request):
    try:
        return json.loads(request.body.decode("utf-8")), None
    except Exception:
        return None, JsonResponse({"detail": "Invalid JSON"}, status=400)


def _require_admin(user):
    if not _is_admin(user):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return None


def _get_customer_or_404(customer_id):
    return get_object_or_404(Customers, id=customer_id)


def _resolve_old_rack_context(cust, payload, request):
    old_rack_id = payload.get("old_rack_id") or request.GET.get("rack_id")

    if old_rack_id:
        old_rk = (
            cust.racks
            .select_related("floor_level__site_location")
            .filter(id=int(old_rack_id))
            .first()
        )
    else:
        old_rk = (
            cust.racks
            .select_related("floor_level__site_location")
            .order_by("id")
            .first()
        )

    return {
        "old_rack_id": old_rack_id,
        "old_rk": old_rk,
        "old_rack": old_rk.name_racks if old_rk else None,
        "old_floor": old_rk.floor_level.name if old_rk and old_rk.floor_level else None,
        "old_site": (
            old_rk.floor_level.site_location.name
            if old_rk and old_rk.floor_level and old_rk.floor_level.site_location
            else None
        ),
    }


def _resolve_group_for_request(cust, payload=None, request=None, *, required=False):
    payload = payload or {}
    group_id = payload.get("group_id") if payload else None
    if not group_id and request is not None:
        group_id = request.GET.get("group_id")

    if group_id:
        return get_object_or_404(ARGroup, id=int(group_id), customer=cust)
    if required:
        raise ValueError("group_id wajib dikirim saat mengedit data customer.")
    return _pick_display_group(cust)


def _apply_group_mailing_lists(cust, grp, raw_mailing_list):
    ml_objs = _ensure_mailing_list_objects(raw_mailing_list)
    group_ars = AR.objects.filter(customer=cust, ar_group=grp)

    if ml_objs:
        for ar in group_ars:
            ar.mailing_lists.set(ml_objs)
    else:
        for ar in group_ars:
            ar.mailing_lists.clear()


def _build_slot_keys_from_payload(ars_payload):
    keys = []
    for item in ars_payload:
        email = _normalize_email(item.get("email") or "")
        name_key = _norm(item.get("authorized_name"))
        phone_key = _norm(item.get("phone"))

        if not email and not name_key and not phone_key:
            continue

        keys.append(email or name_key or phone_key)
    return keys


def _tenants_by_customer_get(request, customer_id):
    cust = _get_customer_or_404(customer_id)

    group_id = request.GET.get("group_id")
    rack_id = request.GET.get("rack_id")

    if group_id:
        grp = get_object_or_404(ARGroup, id=int(group_id), customer=cust)
    else:
        grp = None

    # Gunakan rack yang benar-benar diklik user
    if rack_id:
        rk = (
            cust.racks
            .select_related("floor_level__site_location")
            .filter(id=int(rack_id))
            .first()
        )
    else:
        rk = (
            cust.racks
            .select_related("floor_level__site_location")
            .order_by("id")
            .first()
        )

    if not grp and rk:
        grp = ARGroup.objects.filter(customer=cust, rack=rk).order_by("id").first()
    if not grp:
        grp = _pick_display_group(cust)

    ars = (
        list(
            AR.objects.select_related("ar_group")
            .filter(customer=cust, ar_group=grp)
            .order_by("id")
        )
        if grp else []
    )

    rack_id_val = rk.id if rk else None
    rack_name = rk.name_racks if rk else ""
    floor_id = rk.floor_level.id if rk and rk.floor_level else None
    floor_name = rk.floor_level.name if rk and rk.floor_level else ""
    site_name = (
        rk.floor_level.site_location.name
        if rk and rk.floor_level and rk.floor_level.site_location
        else ""
    )

    mailing_list = _collect_group_mailing_list(cust, grp)

    return JsonResponse({
        "customer_id": cust.id,
        "customer_name": cust.name_customer,
        "customer_site": site_name,
        "rack_location": rack_name,
        "rack_id": rack_id_val,
        "floor_level": floor_name,
        "floor_id": floor_id,
        "group_id": grp.id if grp else None,
        "validity": getattr(grp, "validity_AR", None),
        "date": _safe_date_str(getattr(grp, "due_date", None)),
        "ars": [
            {
                "id": a.id,
                "authorized_name": a.authorized_name,
                "email": a.email_address,
                "phone": a.mobile_phone,
            }
            for a in ars
        ],
        "mailing_list": mailing_list,
    })


def _tenants_by_customer_delete(request, customer_id):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    cust = _get_customer_or_404(customer_id)
    cust_name = cust.name_customer or "-"

    rk = cust.racks.select_related("floor_level__site_location").first()
    rack_name = rk.name_racks if rk else None

    try:
        with transaction.atomic():
            _log_tenant_change(
                user=request.user,
                action="deleted",
                customer=None,
                customer_name=cust_name,
                details={
                    "customer_id": customer_id,
                    "rack": rack_name,
                    "type": "delete-customer",
                }
            )

            AR.objects.filter(customer_id=customer_id).delete()
            Customers.objects.filter(id=customer_id).delete()
            ARGroup.objects.filter(ars__isnull=True).delete()

            return JsonResponse({"status": "deleted"})

    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"detail": "Internal server error"}, status=500)


def _tenants_by_customer_create(request):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    payload, error_response = _parse_json_request(request)
    if error_response:
        return error_response

    # gunakan normalisasi customer name yang lebih kuat
    name = _norm_customer_name(payload.get("customer_name"))
    validity = payload.get("validity")
    due_date = _parse_date(payload.get("date"))
    ars_payload = payload.get("ars") or []

    if not name:
        return JsonResponse({"detail": "Customer Name wajib diisi."}, status=400)

    ok, err = _validate_unique_authorized_emails(ars_payload)
    if not ok:
        return JsonResponse({"detail": err}, status=400)

    try:
        with transaction.atomic():
            # 1) REUSE customer jika nama sama (hindari duplikasi)
            #    lock row existing agar lebih aman dari race sederhana
            cust = (
                Customers.objects
                .select_for_update()
                .filter(name_customer__iexact=name)
                .first()
            )

            customer_created = False
            if not cust:
                cust = Customers.objects.create(
                    name_customer=name,
                    created_by=request.user
                )
                customer_created = True
            else:
                # opsional: lengkapi field yang kosong (tidak wajib)
                fields = []
                incoming_phone = (payload.get("office_phone") or "").strip()
                if incoming_phone and not (cust.office_phone or "").strip():
                    cust.office_phone = incoming_phone
                    fields.append("office_phone")

                incoming_auth = (payload.get("authorized_string") or "").strip()
                if incoming_auth and not (cust.authorized or "").strip():
                    cust.authorized = incoming_auth
                    fields.append("authorized")

                if fields:
                    cust.save(update_fields=fields)

            # 2) resolve site
            site = _get_site(payload)

            # 3) resolve/create floor & rack
            floor, floor_created = _resolve_or_create_floor(site, payload)
            rk, rack_created = _resolve_or_create_rack(floor, payload)

            # 4) LINK customer <-> rack TANPA menghapus rack lain
            #    (tenant list kamu konsepnya Customer×Rack, jadi customer bisa multi-rack)
            cust.racks.add(rk)

            # 5) ensure ARGroup: get_or_create agar tidak duplikat untuk (customer, validity, due_date)
            grp, _ = ARGroup.objects.get_or_create(
                customer=cust,
                rack=rk,
                validity_AR=validity if validity else None,
                due_date=due_date
            )

            # 6) create/update AR (berdasarkan email unik per customer)
            created_ids = []
            updated_ids = []

            for item in ars_payload:
                email = _normalize_email(item.get("email"))
                auth = _norm(item.get("authorized_name"))
                phone = _norm(item.get("phone"))

                # skip baris kosong
                if not email and not auth and not phone:
                    continue

                # kalau mau lebih ketat: jangan buat AR tanpa email (menghindari constraint unik untuk email kosong)
                if not email:
                    continue

                ar_obj, created = AR.objects.get_or_create(
                    customer=cust,
                    ar_group=grp,
                    email_address=email,
                    defaults={
                        "authorized_name": auth,
                        "mobile_phone": phone,
                    }
                )

                if created:
                    created_ids.append(ar_obj.id)
                else:
                    # update jika ada perubahan (dan pastikan group mengarah ke grp yang dipakai list)
                    changed = False
                    if (ar_obj.authorized_name or "") != auth:
                        ar_obj.authorized_name = auth
                        changed = True
                    if (ar_obj.mobile_phone or "") != phone:
                        ar_obj.mobile_phone = phone
                        changed = True
                    if changed:
                        ar_obj.save()
                        updated_ids.append(ar_obj.id)
            
            # 7) apply Mailing List ke semua AR dalam group ini
            _apply_group_mailing_lists(cust, grp, payload.get("mailing_list"))

            _log_tenant_change(
                user=request.user,
                customer=cust,
                action="created" if customer_created else "linked",
                details={
                    "customer_created": customer_created,
                    "site": site.name if site else None,
                    "floor_id": floor.id if floor else None,
                    "floor_level": getattr(floor, "name", None),
                    "rack_id": rk.id if rk else None,
                    "rack_location": getattr(rk, "name_racks", None),
                    "group_id": grp.id,
                    "ar_created": len(created_ids),
                    "ar_updated": len(updated_ids),
                }
            )

            return JsonResponse({
                "status": "created" if customer_created else "linked",
                "customer_id": cust.id,
                "group_id": grp.id,
                "ar_created_ids": created_ids,
                "ar_updated_ids": updated_ids,
                "floor_id": floor.id,
                "rack_id": rk.id,
                "floor_created": floor_created,
                "rack_created": rack_created,
            }, status=201)

    except ValueError as ve:
        return JsonResponse({"detail": str(ve)}, status=400)
    except IntegrityError as ie:
        return JsonResponse({"detail": f"Constraint error: {ie}"}, status=409)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"detail": "Internal server error"}, status=500)


def _tenants_by_customer_update(request, customer_id):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    payload, error_response = _parse_json_request(request)
    if error_response:
        return error_response
    
    cust = _get_customer_or_404(customer_id)
    name = payload.get("customer_name")
    validity = payload.get("validity")
    due_date = _parse_date(payload.get("date"))
    ars_payload = payload.get("ars") or []

    old_name = cust.name_customer
    
    old_ctx = _resolve_old_rack_context(cust, payload, request)
    old_rack_id = old_ctx["old_rack_id"]
    old_rack = old_ctx["old_rack"]
    
    if name is not None and _norm(name) == "":
        return JsonResponse({"detail": "Customer Name wajib diisi."}, status=400)

    ok, err = _validate_unique_authorized_emails(ars_payload)
    if not ok:
        return JsonResponse({"detail": err}, status=400)

    try:
        with transaction.atomic():
            if name:
                cust.name_customer = _norm_customer_name(name)
                cust.save(update_fields=["name_customer"])

            # resolve site + floor + rack (Step 4) lalu set rack
            site = _get_site(payload)
            floor, _ = _resolve_or_create_floor(site, payload)
            rk, _ = _resolve_or_create_rack(floor, payload)

            old_rack_obj = None
            if old_rack_id:
                old_rack_obj = (
                    cust.racks
                    .filter(id=int(old_rack_id))
                    .first()
                )

            # kalau memang pindah ke rack baru, lepas relasi lama
            if old_rack_obj and old_rack_obj.id != rk.id:
                cust.racks.remove(old_rack_obj)

            # pastikan rack baru terhubung
            cust.racks.add(rk)

            # Update/ensure ARGroup
            existing_grp = _resolve_group_for_request(cust, payload=payload, request=request, required=True)

            # snapshot nilai lama untuk log
            old_validity = existing_grp.validity_AR if existing_grp else None
            old_date_str = _safe_date_str(existing_grp.due_date) if existing_grp else ""

            if not existing_grp:
                existing_grp = ARGroup.objects.create(
                    customer=cust,
                    rack=rk,
                    validity_AR=validity if validity else None,
                    due_date=due_date
                )
            else:
                fields = []
                if existing_grp.rack_id != rk.id:
                    existing_grp.rack = rk
                    fields.append("rack")
                if validity is not None:
                    existing_grp.validity_AR = validity
                    fields.append("validity_AR")
                if due_date is not None:
                    existing_grp.due_date = due_date
                    fields.append("due_date")
                if fields:
                    collision = ARGroup.objects.filter(
                        customer=cust,
                        rack=existing_grp.rack,
                        validity_AR=existing_grp.validity_AR,
                        due_date=existing_grp.due_date,
                    ).exclude(id=existing_grp.id).exists()
                    if collision:
                        raise ValueError(
                            "AR Group dengan validity dan due date yang sama sudah ada untuk customer ini."
                        )
                    existing_grp.save(update_fields=fields)

            existing_ars = list(
                AR.objects.select_for_update().filter(customer=cust, ar_group=existing_grp).order_by("id")
            )
            old_slot_keys = [
                (_normalize_email(a.email_address) or _norm(a.authorized_name) or f"slot-{idx+1}")
                for idx, a in enumerate(existing_ars)
            ]
            existing_by_id = {a.id: a for a in existing_ars}
            submitted_existing_ids = set()
            desired = []

            for idx, item in enumerate(ars_payload, start=1):
                final_email = _normalize_email(item.get("email") or "")
                final_name = _norm(item.get("authorized_name"))
                final_phone = _norm(item.get("phone"))
                raw_id = item.get("id")

                if not final_email and not final_name and not final_phone:
                    continue
                if not final_email:
                    raise ValueError(f"Email wajib diisi untuk Authorized Person #{idx}.")

                ar_id = None
                if raw_id not in (None, "", 0, "0"):
                    try:
                        ar_id = int(raw_id)
                    except (TypeError, ValueError):
                        raise ValueError(f"Invalid Authorized Person id: {raw_id}")
                    if ar_id not in existing_by_id:
                        raise ValueError("Authorized Person tidak termasuk customer/group yang sedang diedit.")
                    if ar_id in submitted_existing_ids:
                        raise ValueError("Authorized Person yang sama dikirim lebih dari satu kali.")
                    submitted_existing_ids.add(ar_id)

                desired.append({
                    "id": ar_id,
                    "email": final_email,
                    "name": final_name,
                    "phone": final_phone,
                })

            # Hapus record existing yang memang dihapus dari UI.
            delete_ids = set(existing_by_id) - submitted_existing_ids
            if delete_ids:
                AR.objects.filter(id__in=delete_ids, customer=cust, ar_group=existing_grp).delete()

            # Temporarily move changed existing emails out of the unique-key space.
            temp_targets = []
            for item in desired:
                if not item["id"]:
                    continue
                obj = existing_by_id[item["id"]]
                if _normalize_email(obj.email_address) != item["email"]:
                    obj.email_address = f"__swap__{uuid.uuid4().hex}@swap.local"
                    temp_targets.append(obj)
            if temp_targets:
                AR.objects.bulk_update(temp_targets, ["email_address"])

            final_ar_ids = []
            for item in desired:
                if item["id"]:
                    obj = existing_by_id[item["id"]]
                    obj.email_address = item["email"]
                    obj.authorized_name = item["name"]
                    obj.mobile_phone = item["phone"]
                    obj.ar_group = existing_grp
                    obj.save(update_fields=["email_address", "authorized_name", "mobile_phone", "ar_group", "updated_at"])
                else:
                    # Reuse an existing AR for this customer only when it is not part of another group update.
                    obj = AR.objects.filter(
                        customer=cust, ar_group=existing_grp, email_address__iexact=item["email"]
                    ).first()
                    if not obj:
                        obj = AR.objects.create(
                            customer=cust,
                            ar_group=existing_grp,
                            email_address=item["email"],
                            authorized_name=item["name"],
                            mobile_phone=item["phone"],
                        )
                    else:
                        obj.authorized_name = item["name"]
                        obj.mobile_phone = item["phone"]
                        obj.save(update_fields=["authorized_name", "mobile_phone", "updated_at"])
                final_ar_ids.append(obj.id)

            _apply_group_mailing_lists(cust, existing_grp, payload.get("mailing_list"))

            # gunakan rack/floor/site yang dipilih user
            new_rk = rk
            new_rack = new_rk.name_racks if new_rk else None

            # bangun urutan slot AR baru untuk deteksi reorder / swap
            new_slot_keys = _build_slot_keys_from_payload(ars_payload)

            log_details = {}

            # 1) Kalau rack berubah, hanya log rack
            if old_rack != new_rack:
                log_details["rack_moved"] = {
                    "from": old_rack,
                    "to": new_rack,
                }

            else:
                # 2) Kalau rack tidak berubah, cek AR reorder / swap
                if old_slot_keys and new_slot_keys and old_slot_keys != new_slot_keys:
                    if sorted(old_slot_keys) == sorted(new_slot_keys):
                        moves = []
                        for i, key in enumerate(old_slot_keys):
                            if key in new_slot_keys:
                                new_pos = new_slot_keys.index(key) + 1
                                old_pos = i + 1
                                if new_pos != old_pos:
                                    moves.append(f"{old_pos}→{new_pos}")

                        if moves:
                            log_details["ar_reordered"] = moves

                # 3) Kalau bukan reorder, baru cek perubahan nama customer
                elif old_name != cust.name_customer:
                    log_details["customer_name"] = {
                        "from": old_name,
                        "to": cust.name_customer,
                    }

                # 4) Kalau bukan nama, cek validity
                elif payload.get("validity") is not None and payload.get("validity") != old_validity:
                    log_details["validity"] = {
                        "from": old_validity,
                        "to": payload.get("validity"),
                    }

                # 5) Kalau bukan validity, cek date
                elif payload.get("date") is not None and payload.get("date") != old_date_str:
                    log_details["date"] = {
                        "from": old_date_str,
                        "to": payload.get("date"),
                    }
            
            _log_tenant_change(
                user=request.user,
                customer=cust,
                action="updated",
                details=log_details
            )

            return JsonResponse({"status": "updated"})

    except ValueError as ve:
        return JsonResponse({"detail": str(ve)}, status=400)
    except IntegrityError as ie:
        return JsonResponse({"detail": f"Constraint error: {ie}"}, status=409)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"detail": "Internal server error"}, status=500)


# ---------------------------------------------------------------------
# TENANTS BY CUSTOMER (GROUP CREATE/EDIT/DELETE)
# ---------------------------------------------------------------------
@login_required
@require_http_methods(["GET", "PUT", "DELETE", "POST"])
@csrf_protect
def tenants_by_customer_api(request, customer_id=None):
    """
    CRUD berbasis customer (grup AR):
    - POST (admin): buat customer baru, validasi 3 AR unik, resolve/create floor & rack, buat ARGroup, buat AR.
    - GET : ambil detail customer + rack/floor/site pertama + daftar AR.
    - PUT (admin): update nama, ARGroup, 3 AR, dan update rack (resolve/create).
    - DELETE (admin): hapus semua AR milik customer, lalu customer; bersihkan orphan ARGroup.
    """

    # ----------------- CREATE -----------------
    if request.method == "POST" and customer_id is None:
        return _tenants_by_customer_create(request)

    # ----------------- RETRIEVE -----------------
    if request.method == "GET":
        return _tenants_by_customer_get(request, customer_id)
    
    # ----------------- UPDATE -----------------
    if request.method == "PUT":
        return _tenants_by_customer_update(request, customer_id)

    # ----------------- DELETE -----------------
    if request.method == "DELETE":
        return _tenants_by_customer_delete(request, customer_id)
    
    return JsonResponse({"detail": "Method not allowed"}, status=405)


# ---------------------------------------------------------------------
# AUTOCOMPLETE HELPERS
# ---------------------------------------------------------------------
def _autocomplete_limit(request, default=20, max_limit=50):
    """
    Ambil limit dari querystring, fallback default,
    dan batasi dengan max_limit.
    """
    limit = _parse_positive_int(request.GET.get("limit"), default)
    return min(limit, max_limit)


def _json_id_name_list(qs, *, id_attr="id", name_attr="name", limit=20):
    """
    Serialize queryset/model list menjadi [{id, name}, ...]
    """
    results = []
    for obj in qs[:limit]:
        results.append({
            "id": getattr(obj, id_attr),
            "name": getattr(obj, name_attr),
        })
    return results


@login_required
@require_http_methods(["GET"])
def floor_autocomplete_api(request):
    site_id = request.GET.get("site_id")
    site_name = _norm(request.GET.get("site"))
    q = _norm(request.GET.get("q"))
    limit = _autocomplete_limit(request)

    if not site_id and site_name:
        site = SiteLocation.objects.filter(name__iexact=site_name).first()
        if not site:
            return JsonResponse({"detail": f"Site '{site_name}' tidak ditemukan."}, status=404)
        site_id = site.id

    site_id = _parse_positive_int(site_id, None)
    if not site_id:
        return JsonResponse({"detail": "site_id is required"}, status=400)

    qs = FloorLevel.objects.filter(site_location_id=site_id).order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)

    data = _json_id_name_list(qs, id_attr="id", name_attr="name", limit=limit)
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["GET"])
def rack_autocomplete_api(request):
    """
    GET /api/racks/autocomplete/?floor_id=<int>&q=<string>
    Return list rack pada floor tertentu yang match query.
    """
    floor_id = _parse_positive_int(request.GET.get("floor_id"), None)
    q = _norm(request.GET.get("q"))
    limit = _autocomplete_limit(request)

    if not floor_id:
        return JsonResponse({"detail": "floor_id is required"}, status=400)

    qs = Rack.objects.filter(floor_level_id=floor_id).order_by("name_racks")
    if q:
        qs = qs.filter(name_racks__icontains=q)

    data = _json_id_name_list(qs, id_attr="id", name_attr="name_racks", limit=limit)
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["GET"])
def customer_autocomplete_api(request):
    q = _norm(request.GET.get("q"))
    limit = _autocomplete_limit(request)

    if not q:
        return JsonResponse([], safe=False)

    qs = (
        Customers.objects
        .filter(name_customer__icontains=q)
        .order_by("name_customer")
    )

    data = _json_id_name_list(qs, id_attr="id", name_attr="name_customer", limit=limit)
    return JsonResponse(data, safe=False)


# ---------------------------------------------------------------------
# PREFILL EDIT TENANTS HELPERS
# ---------------------------------------------------------------------
def _get_default_customer_rack(cust):
    """
    Ambil rack default customer untuk prefill cepat.
    Saat ini strategi: rack dengan id terkecil.
    """
    return (
        cust.racks
        .select_related("floor_level__site_location")
        .order_by("id")
        .first()
    )


def _serialize_ar_prefill(ar):
    return {
        "id": ar.id,
        "authorized_name": ar.authorized_name or "",
        "email": ar.email_address or "",
        "phone": ar.mobile_phone or "",
    }


# ---------------------------------------------------------------------
# PREFILL EDIT TENANTS
# ---------------------------------------------------------------------
@login_required
@require_http_methods(["GET"])
def customer_prefill_api(request, customer_id):
    """
    Prefill cepat berdasarkan customer yang dipilih dari autocomplete.
    Menggunakan:
    - rack default customer
    - display group customer
    - seluruh Authorized Person pada group
    """
    cust = _get_customer_or_404(customer_id)

    rk = _get_default_customer_rack(cust)

    site_name = (
        rk.floor_level.site_location.name
        if rk and rk.floor_level and rk.floor_level.site_location
        else ""
    )
    floor_name = rk.floor_level.name if rk and rk.floor_level else ""
    floor_id = rk.floor_level.id if rk and rk.floor_level else None
    rack_name = rk.name_racks if rk else ""
    rack_id = rk.id if rk else None

    grp = _pick_display_group(cust)
    validity = grp.validity_AR if grp else None
    due_date = grp.due_date.isoformat() if (grp and grp.due_date) else None

    ars = []
    if grp:
        qs = (
            AR.objects
            .filter(customer=cust, ar_group=grp)
            .order_by("id")
        )
        ars = [_serialize_ar_prefill(a) for a in qs]

    mailing_list = _collect_group_mailing_list(cust, grp)

    return JsonResponse({
        "customer_id": cust.id,
        "customer_name": cust.name_customer or "",
        "customer_site": site_name,
        "floor_id": floor_id,
        "floor_level": floor_name,
        "rack_id": rack_id,
        "rack_location": rack_name,
        "group_id": grp.id if grp else None,
        "validity": validity,
        "date": due_date,
        "ars": ars,
        "mailing_list": mailing_list,
    })


# ---------------------------------------------------------------------
# TENANTS BY CUSTOMER (DELETE ROW CUSTOMER-RACK)
# ---------------------------------------------------------------------
@login_required
@require_http_methods(["DELETE"])
@csrf_protect
def delete_customer_rack_api(request, customer_id, rack_id):
    """
    Hapus SATU relasi Customer <-> Rack pada tabel penghubung (customer_racks).
    Tidak menghapus customer dan tidak menghapus rack object.
    Admin-only.
    """
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden

    cust = _get_customer_or_404(customer_id)
    rk = get_object_or_404(Rack, id=rack_id)

    try:
        with transaction.atomic():
            # Hapus relasi M2M saja
            cust.racks.remove(rk)

            _log_tenant_change(
                user=request.user,
                action="row-deleted",
                customer=cust,
                customer_name=cust.name_customer,
                details={
                    "customer_id": customer_id,
                    "rack_id": rack_id,
                    "rack": rk.name_racks,
                    "type": "delete-row-customer-rack",
                }
            )

        return JsonResponse({
            "status": "deleted-row",
            "customer_id": customer_id,
            "rack_id": rack_id,
        }, status=200)

    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"detail": "Internal server error"}, status=500)


# ---------------------------------------------------------------------
# TENANTS ADD PAGE HELPERS
# ---------------------------------------------------------------------
def _get_tenants_add_page_context():
    site_locations = SiteLocation.objects.all()

    floor_levels = (
        FloorLevel.objects
        .select_related("site_location")
        .order_by("site_location__name", "name")
    )

    racks = (
        Rack.objects
        .select_related("floor_level__site_location")
        .order_by("floor_level__site_location__name", "floor_level__name", "name_racks")
    )

    return {
        "site_locations": site_locations,
        # Keep both keys for backward compatibility. tenant_add.html uses
        # `floor_levels`, while some legacy views/components still reference
        # `floor_levels_distinct`. Both point to the same site-scoped queryset.
        "floor_levels": floor_levels,
        "floor_levels_distinct": floor_levels,
        "racks": racks,
        "mailing_lists": MailingList.objects.order_by("name"),
    }


# ---------------------------------------------------------------------
# TENANTS ADD PAGE
# ---------------------------------------------------------------------
@login_required
def tenants_add_page(request):
    """
    Render halaman penambahan tenant:
    - Menyediakan site locations
    - Menyediakan floor levels
    - Menyediakan racks untuk dropdown/autocomplete
    """
    context = {
        "active_menu": "tenants",
        **_get_tenants_add_page_context(),
    }
    return render(request, "components/tenant_add.html", context)


# ---------------------------------------------------------------------
# MAILING RECIPIENT RESOLVER
# ---------------------------------------------------------------------
def _unique_normalized_emails(values):
    result = []
    seen = set()
    for value in values:
        email = _normalize_email(value)
        if not email or email in seen:
            continue
        seen.add(email)
        result.append(email)
    return result


def _parse_additional_mailing_list_values(raw):
    """Return unique, validated email addresses from string/list input."""
    if raw is None:
        return []
    values = raw if isinstance(raw, (list, tuple, set)) else re.split(r"[;,\n]+", str(raw))
    emails = []
    for value in values:
        email = _normalize_email(value)
        if not email:
            continue
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(f"Additional Mailing List tidak valid: {value}")
        emails.append(email)
    return _unique_normalized_emails(emails)


def _additional_mailing_emails_for_customers(customer_ids):
    return _unique_normalized_emails(
        CustomerAdditionalMailingList.objects
        .filter(customer_id__in=list(customer_ids))
        .values_list("email_address", flat=True)
    )


def _sync_customer_additional_mailing_lists(customer, raw_values):
    emails = _parse_additional_mailing_list_values(raw_values)
    CustomerAdditionalMailingList.objects.filter(customer=customer).exclude(email_address__in=emails).delete()
    existing = {x.email_address.lower(): x for x in CustomerAdditionalMailingList.objects.filter(customer=customer)}
    for email in emails:
        if email not in existing:
            CustomerAdditionalMailingList.objects.create(customer=customer, email_address=email)
    return emails


def _active_ar_emails_for_customers(customer_ids):
    today = timezone.localdate()
    emails = []
    for ar in AR.objects.filter(customer_id__in=list(customer_ids)).select_related("ar_group").order_by("id"):
        validity, due_date, state = _effective_ar_validity(ar)
        if state["key"] == "expired":
            continue
        emails.append(ar.email_address)
    return _unique_normalized_emails(emails)


def _customer_ids_for_location(*, site_id=None, floor_id=None, customer_id=None):
    qs = Customers.objects.filter(racks__isnull=False)
    if site_id:
        qs = qs.filter(racks__floor_level__site_location_id=site_id)
    if floor_id:
        qs = qs.filter(racks__floor_level_id=floor_id)
    if customer_id:
        qs = qs.filter(id=customer_id)
    return list(qs.values_list("id", flat=True).distinct())


def _emails_for_location(*, site_id=None, floor_id=None, customer_id=None):
    """v1.8: match impacted customers by rack location, then notify all active ARs of each customer."""
    customer_ids = _customer_ids_for_location(site_id=site_id, floor_id=floor_id, customer_id=customer_id)
    return _active_ar_emails_for_customers(customer_ids)


def _emails_for_mailing_group(group_id):
    group = (
        MailingGroup.objects
        .filter(id=group_id, is_active=True)
        .select_related("site")
        .prefetch_related("floors", "specific_customers")
        .first()
    )
    if not group:
        return [], None
    floor_ids = list(group.floors.values_list("id", flat=True))
    customer_ids = set(group.specific_customers.values_list("id", flat=True))
    if floor_ids:
        customer_ids.update(Customers.objects.filter(
            racks__floor_level__site_location_id=group.site_id,
            racks__floor_level_id__in=floor_ids,
        ).values_list("id", flat=True).distinct())
    customer_ids = list(customer_ids)
    return {
        "ar": _active_ar_emails_for_customers(customer_ids),
        "additional": _additional_mailing_emails_for_customers(customer_ids),
        "customer_ids": customer_ids,
    }, group

def _dedupe_recipient_fields(to_list, cc_list, bcc_list):
    """Cross-field priority required by MailGenix: TO > CC > BCC."""
    to_list = _unique_normalized_emails(to_list)
    to_seen = set(to_list)
    cc_list = [e for e in _unique_normalized_emails(cc_list) if e not in to_seen]
    cc_seen = set(cc_list)
    bcc_list = [
        e for e in _unique_normalized_emails(bcc_list)
        if e not in to_seen and e not in cc_seen
    ]
    return to_list, cc_list, bcc_list


@login_required
@require_http_methods(["GET"])
def mailing_recipients_api(request):
    """Resolve MailGenix recipients using location-aware rules.

    Confirmed rules:
    - Specific Customer + selected site/floor: all active ARs of the impacted customer -> TO.
    - Specific Customer: customer Additional Mailing List -> CC.
    - Bulk Site/Floor: matching customers' active ARs + Additional Mailing Lists -> BCC.
    - Mailing Group bulk: matching customers' active ARs + Additional Mailing Lists -> BCC.
    - Existing/internal operational CC addresses remain in CC.
    - Cross-field dedupe priority: TO > CC > BCC.
    """
    site_id = _parse_positive_int(request.GET.get("site_id"), None)
    floor_id = _parse_positive_int(request.GET.get("floor_id"), None)
    customer_id = _parse_positive_int(request.GET.get("customer_id"), None)
    group_id = _parse_positive_int(request.GET.get("mailing_group"), None)

    fixed_to = ["nttapac.id.noc@global.ntt"]
    fixed_cc = []

    # Mailing Group is database-driven Site + Floor scope.
    if group_id:
        group_recips, group = _emails_for_mailing_group(group_id)
        if not group:
            return JsonResponse({"detail": "Mailing List Group tidak valid atau tidak aktif."}, status=400)
        floor_names = sorted(list(group.floors.values_list("name", flat=True)), key=_natural_floor_sort_key)
        ar_emails = list(group_recips.get("ar", []))
        additional_emails = list(group_recips.get("additional", []))
        bulk_bcc = ar_emails + additional_emails
        to_list, cc_list, bcc_list = _dedupe_recipient_fields(fixed_to, fixed_cc, bulk_bcc)
        return JsonResponse({
            "mode": "mailing-group-bulk", "mailing_group": group.id,
            "mailing_group_name": group.name,
            "site": group.site.name, "floors": floor_names,
            "to": to_list, "cc": cc_list, "bcc": bcc_list,
            "counts": {"to": len(to_list), "cc": len(cc_list), "bcc": len(bcc_list)},
            "scope_summary": {
                "matched_customers": len(group_recips.get("customer_ids", [])),
                "active_ar": len(_unique_normalized_emails(ar_emails)),
                "additional_mailing_lists": len(_unique_normalized_emails(additional_emails)),
                "unique_bcc": len(bcc_list),
            },
        })

    if not site_id or not floor_id:
        return JsonResponse({"detail": "site_id dan floor_id wajib dipilih."}, status=400)

    floor = FloorLevel.objects.select_related("site_location").filter(id=floor_id, site_location_id=site_id).first()
    if not floor:
        return JsonResponse({"detail": "Floor tidak sesuai dengan site yang dipilih."}, status=400)

    customer_ids = _customer_ids_for_location(site_id=site_id, floor_id=floor_id, customer_id=customer_id)
    scope_ar_emails = _active_ar_emails_for_customers(customer_ids)
    scope_additional = _additional_mailing_emails_for_customers(customer_ids)
    if customer_id:
        # Specific Customer: customer AR -> TO, customer Additional Mailing List -> CC.
        to_list, cc_list, bcc_list = _dedupe_recipient_fields(scope_ar_emails, list(fixed_cc) + scope_additional, [])
        mode = "specific-customer"
    else:
        # Bulk Site/Floor: both customer AR and Additional Mailing List -> BCC.
        bulk_bcc = list(scope_ar_emails) + list(scope_additional)
        to_list, cc_list, bcc_list = _dedupe_recipient_fields(fixed_to, fixed_cc, bulk_bcc)
        mode = "site-floor-bulk"

    return JsonResponse({
        "mode": mode, "site": floor.site_location.name, "floor": floor.name, "mailing_group": None,
        "to": to_list, "cc": cc_list, "bcc": bcc_list,
        "counts": {"to": len(to_list), "cc": len(cc_list), "bcc": len(bcc_list)},
        "scope_summary": {
            "matched_customers": len(customer_ids),
            "active_ar": len(_unique_normalized_emails(scope_ar_emails)),
            "additional_mailing_lists": len(_unique_normalized_emails(scope_additional)),
            "unique_bcc": len(bcc_list),
        },
    })


# ---------------------------------------------------------------------
# MAILING GROUP MANAGEMENT
# ---------------------------------------------------------------------
def _serialize_mailing_group(group):
    floors = sorted(list(group.floors.values("id", "name")), key=lambda f: _natural_floor_sort_key(f["name"]))
    explicit_customers = list(group.specific_customers.values("id", "name_customer"))
    return {
        "id": group.id,
        "name": group.name,
        "site_id": group.site_id,
        "site_name": group.site.name,
        "floors": floors,
        "specific_customers": explicit_customers,
        "description": group.description or "",
        "is_active": group.is_active,
        "member_count": len(_active_ar_emails_for_customers(
            Customers.objects.filter(
                racks__floor_level__site_location_id=group.site_id,
                racks__floor_level_id__in=[f["id"] for f in floors],
            ).values_list("id", flat=True).distinct()
        )) if floors else 0,
    }


@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def mailing_groups_api(request):
    if request.method == "GET":
        groups = MailingGroup.objects.select_related("site").prefetch_related("floors", "specific_customers").all()
        return JsonResponse({"groups": [_serialize_mailing_group(g) for g in groups]})

    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON tidak valid."}, status=400)
    name = _norm(payload.get("name"))
    site_id = _parse_positive_int(payload.get("site_id"), None)
    floor_ids = [int(x) for x in payload.get("floor_ids", []) if str(x).isdigit()]
    customer_ids = [int(x) for x in payload.get("customer_ids", []) if str(x).isdigit()]
    if not name or not site_id or (not floor_ids and not customer_ids):
        return JsonResponse({"detail": "Name, Site, dan minimal satu Floor atau Specific Customer wajib diisi."}, status=400)
    site = get_object_or_404(SiteLocation, id=site_id)
    valid_floors = list(FloorLevel.objects.filter(id__in=floor_ids, site_location=site))
    if len(valid_floors) != len(set(floor_ids)):
        return JsonResponse({"detail": "Ada Floor yang tidak sesuai dengan Site."}, status=400)
    if MailingGroup.objects.filter(name__iexact=name).exists():
        return JsonResponse({"detail": "Nama Mailing Group sudah digunakan."}, status=409)
    with transaction.atomic():
        group = MailingGroup.objects.create(
            name=name, site=site, description=_norm(payload.get("description")),
            is_active=bool(payload.get("is_active", True)),
        )
        group.floors.set(valid_floors)
        group.specific_customers.set(Customers.objects.filter(id__in=customer_ids))
        _record_activity(user=request.user, action="create", entity_type="MailingGroup", entity_id=group.id, entity_label=group.name, description=f"Created mailing group {group.name}")
    return JsonResponse(_serialize_mailing_group(group), status=201)


@login_required
@require_http_methods(["PUT", "DELETE"])
@csrf_protect
def mailing_group_detail_api(request, group_id):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden
    group = get_object_or_404(MailingGroup.objects.select_related("site").prefetch_related("floors", "specific_customers"), id=group_id)
    if request.method == "DELETE":
        label = group.name
        group.delete()
        _record_activity(user=request.user, action="delete", entity_type="MailingGroup", entity_id=group_id, entity_label=label, description=f"Deleted mailing group {label}")
        return JsonResponse({"status": "deleted"})
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON tidak valid."}, status=400)
    name = _norm(payload.get("name"))
    site_id = _parse_positive_int(payload.get("site_id"), None)
    floor_ids = [int(x) for x in payload.get("floor_ids", []) if str(x).isdigit()]
    customer_ids = [int(x) for x in payload.get("customer_ids", []) if str(x).isdigit()]
    if not name or not site_id or (not floor_ids and not customer_ids):
        return JsonResponse({"detail": "Name, Site, dan minimal satu Floor atau Specific Customer wajib diisi."}, status=400)
    site = get_object_or_404(SiteLocation, id=site_id)
    valid_floors = list(FloorLevel.objects.filter(id__in=floor_ids, site_location=site))
    if len(valid_floors) != len(set(floor_ids)):
        return JsonResponse({"detail": "Ada Floor yang tidak sesuai dengan Site."}, status=400)
    if MailingGroup.objects.filter(name__iexact=name).exclude(id=group.id).exists():
        return JsonResponse({"detail": "Nama Mailing Group sudah digunakan."}, status=409)
    with transaction.atomic():
        group.name = name
        group.site = site
        group.description = _norm(payload.get("description"))
        group.is_active = bool(payload.get("is_active", True))
        group.save(update_fields=["name", "site", "description", "is_active", "updated_at"])
        group.floors.set(valid_floors)
        group.specific_customers.set(Customers.objects.filter(id__in=customer_ids))
        _record_activity(user=request.user, action="update", entity_type="MailingGroup", entity_id=group.id, entity_label=group.name, description=f"Updated mailing group {group.name}")
    return JsonResponse(_serialize_mailing_group(group))


# ---------------------------------------------------------------------
# EMAIL TEMPLATE RENDER
# ---------------------------------------------------------------------
@login_required
@require_POST
@csrf_protect
def render_email_template(request):
    payload = {k: request.POST.get(k, "") for k in request.POST.keys()}
    category = _norm(payload.get("type_notification") or payload.get("category"))
    render_payload = {k:v for k,v in payload.items() if k not in {"type_notification", "category"}}
    html_body = _render_notification_html(type_notification=category, request=request, **render_payload)
    if not html_body:
        return JsonResponse({"detail": f"Invalid notification type: {category}"}, status=400)
    aliases={"outage report notification":"outage","maintenance notification":"preventive-maintenance","sharing information notification":"sharing-information","site access request":"site-access","general cleaning notification":"general-cleaning","response alarm notification":"response-alarm"}
    cat=aliases.get(category.lower(),category.lower())
    return JsonResponse({"html": _prepare_browser_preview_html(html_body), "subject": _notification_subject(cat,payload)})


# ---------------------------------------------------------------------
# EMAIL TEMPLATE EML
# ---------------------------------------------------------------------
@login_required
@require_POST
@csrf_protect
def compose_email_eml(request):
    try:
        payload = {k: request.POST.get(k, "") for k in request.POST.keys()}
        category = _norm(payload.get("type_notification") or payload.get("category"))
        aliases={"outage report notification":"outage","maintenance notification":"preventive-maintenance","sharing information notification":"sharing-information","site access request":"site-access","general cleaning notification":"general-cleaning","response alarm notification":"response-alarm"}
        cat=aliases.get(category.lower(),category.lower())
        render_payload = {k:v for k,v in payload.items() if k not in {"type_notification", "category"}}
        html = _render_notification_html(type_notification=cat, request=request, **render_payload)
        if not html:
            return JsonResponse({"detail": f"Invalid notification type: {category}"}, status=400)
        to_raw=_norm(payload.get("to")); cc_raw=_norm(payload.get("cc")); bcc_raw=_norm(payload.get("bcc"))
        subject=_notification_subject(cat,payload)
        html_for_eml, inline_assets = _prepare_eml_html_and_assets(html)
        plain=_simple_html_to_text(html_for_eml)
        msg=StdEmailMessage(policy=SMTP); msg["Subject"]=subject
        if to_raw: msg["To"]=to_raw
        if cc_raw: msg["Cc"]=cc_raw
        if bcc_raw: msg["Bcc"]=bcc_raw
        msg["X-Unsent"]="1"
        msg.set_content(plain); msg.add_alternative(html_for_eml, subtype="html")
        _attach_inline_assets(msg.get_payload()[-1], inline_assets)
        _record_activity(user=request.user, action="generate_notification", entity_type="Notification", entity_label=cat, description=f"Generated {cat}", metadata={"notification_type":cat,"site":payload.get("site") or payload.get("customer_site"),"to_count":len(_unique_normalized_emails(re.split(r"[;,]",to_raw))) if to_raw else 0,"cc_count":len(_unique_normalized_emails(re.split(r"[;,]",cc_raw))) if cc_raw else 0,"bcc_count":len(_unique_normalized_emails(re.split(r"[;,]",bcc_raw))) if bcc_raw else 0,"subject":subject,"variant":payload.get("variant"),"subcategory":payload.get("subcategory"),"update_type":payload.get("update_type")})
        def clean_filename(value):
            value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
            return re.sub(r"_+", "_", value).strip("_") or "NA"
        site_token=clean_filename(payload.get("site") or payload.get("customer_site") or "SITE")
        ticket_token=clean_filename(payload.get("ticket_number") or "TICKET")
        category_names={
            "outage":"Outage", "preventive-maintenance":"PreventiveMaintenance",
            "response-alarm":"ResponseAlarm", "general-cleaning":"GeneralCleaning",
            "site-access":"SiteAccess", "sharing-information":"SharingInformation",
        }
        category_token=category_names.get(cat, clean_filename(cat).replace("_",""))
        # Outage uses update type (Occurrence/StatusUpdate/Recovery/RootCause).
        # Other categories use the selected template subtype (Fire, Flooding, PreventiveMaintenance, etc.).
        selected_type=(payload.get("update_type") if cat=="outage" else payload.get("subcategory")) or "Notification"
        type_token=clean_filename(selected_type).replace("_","")
        variant_token=clean_filename(payload.get("variant") or "General")
        filename=f"{site_token}_{ticket_token}_{category_token}_{type_token}_{variant_token}.eml"
        response=HttpResponse(msg.as_bytes(),content_type="message/rfc822"); response["Content-Disposition"]=f'attachment; filename="{filename}"'; return response
    except Exception as e:
        logger.error("compose_email_eml failed: %s",e,exc_info=True); return JsonResponse({"detail":str(e)},status=500)



@login_required
@require_http_methods(["GET"])
def live_state_api(request):
    latest = ActivityLog.objects.order_by("-id").values("id", "created_at").first()
    return JsonResponse({
        "revision": latest["id"] if latest else 0,
        "updated_at": latest["created_at"].isoformat() if latest else timezone.now().isoformat(),
        "counts": {
            "customers": Customers.objects.count(),
            "support_groups": SupportGroup.objects.count(),
            "mailing_groups": MailingGroup.objects.count(),
            "activity": ActivityLog.objects.count(),
        },
    })

# ---------------------------------------------------------------------
# CUSTOMER WORKSPACE / SUPPORT GROUP
# ---------------------------------------------------------------------
def _date_iso(value):
    return value.isoformat() if value else ""


def _status_from_due_date(due_date, validity=None):
    """Display status is date-driven: Active / Expiring Soon / Expired."""
    today = timezone.localdate()
    if validity == ARGroup.VALIDITY_EXPIRED:
        return {"key": "expired", "label": "Expired", "next_date": _date_iso(due_date)}
    if not due_date:
        return {"key": "active", "label": "Active", "next_date": ""}
    if due_date < today:
        return {"key": "expired", "label": "Expired", "next_date": _date_iso(due_date)}
    if (due_date - today).days <= 30:
        return {"key": "expiring", "label": "Expiring Soon", "next_date": _date_iso(due_date)}
    return {"key": "active", "label": "Active", "next_date": _date_iso(due_date)}


def _effective_ar_validity(ar):
    validity = ar.validity or getattr(ar.ar_group, "validity_AR", None) or ARGroup.VALIDITY_VALID
    due_date = ar.due_date or getattr(ar.ar_group, "due_date", None)
    return validity, due_date, _status_from_due_date(due_date, validity)


def _customer_status(customer):
    """Customer badge from Authorized Person and Support Group validity dates."""
    statuses = []
    dates = []
    ars = list(customer.ars.select_related("ar_group").all())
    for ar in ars:
        validity, due_date, state = _effective_ar_validity(ar)
        statuses.append(state)
        if due_date:
            dates.append(due_date)
    for sg in customer.support_groups.all():
        state = _status_from_due_date(sg.validity_date, sg.status)
        statuses.append(state)
        if sg.validity_date:
            dates.append(sg.validity_date)

    if not statuses:
        return {"key": "active", "label": "Active", "next_date": ""}
    if any(x["key"] == "active" for x in statuses):
        future = sorted(d for d in dates if d >= timezone.localdate())
        return {"key": "active", "label": "Active", "next_date": _date_iso(future[0]) if future else ""}
    if any(x["key"] == "expiring" for x in statuses):
        future = sorted(d for d in dates if d >= timezone.localdate())
        return {"key": "expiring", "label": "Expiring Soon", "next_date": _date_iso(future[0]) if future else ""}
    return {"key": "expired", "label": "Expired", "next_date": _date_iso(max(dates)) if dates else ""}

def _rack_payload(rack, group_id=None):
    floor = rack.floor_level
    site = floor.site_location
    return {
        "rack_id": rack.id,
        "group_id": group_id,
        "site": site.name,
        "floor": floor.name,
        "rack": rack.name_racks,
        "description": floor.desc or "",
    }


def _support_payload(item):
    rack = item.rack
    floor = rack.floor_level if rack else None
    site = floor.site_location if floor else None
    return {
        "id": item.id,
        "customer_id": item.customer_id,
        "rack_id": item.rack_id,
        "site": site.name if site else "",
        "floor": floor.name if floor else "",
        "rack": rack.name_racks if rack else "",
        "name": item.name,
        "identity_number": item.identity_number or "",
        "access_level": item.access_level or "",
        "email_phone": item.email_phone or "",
        "reference_info": item.reference_info or "",
        "notes": item.notes or "",
        "validity_date": _date_iso(item.validity_date),
        "status": item.status,
    }


@login_required
def customer_explorer_api(request):
    customers = (
        Customers.objects
        .prefetch_related(
            "racks__floor_level__site_location", "ar_groups", "support_groups"
        )
        .order_by("name_customer", "id")
    )
    sites = {}
    for customer in customers:
        status = _customer_status(customer)
        seen_sites = set()
        for rack in customer.racks.all():
            site_name = rack.floor_level.site_location.name
            if site_name in seen_sites:
                continue
            seen_sites.add(site_name)
            sites.setdefault(site_name, []).append({
                "id": customer.id,
                "name": customer.name_customer or "-",
                "status": status,
                "authorized_count": customer.ars.count(),
                "support_count": customer.support_groups.count(),
            })
    return JsonResponse({
        "sites": [
            {"name": name, "customers": items, "count": len(items)}
            for name, items in sorted(sites.items(), key=lambda x: x[0].lower())
        ],
        "total_customers": customers.count(),
    })


@login_required
def customer_workspace_api(request, customer_id):
    customer = get_object_or_404(
        Customers.objects.prefetch_related(
            "racks__floor_level__site_location",
            "ars__ar_group",
            "ars__mailing_lists",
            "support_groups__rack__floor_level__site_location",
            "associations__rack__floor_level__site_location",
        ),
        id=customer_id,
    )
    site_filter = (request.GET.get("site") or "").strip()
    racks = list(customer.racks.all())
    if site_filter:
        racks = [r for r in racks if r.floor_level.site_location.name == site_filter]

    # v1.8: Authorized Persons belong to the customer, not to a rack.
    # Existing legacy location-scoped ARs are deduplicated by email for display.
    authorized = []
    seen_emails = set()
    for ar in customer.ars.select_related("ar_group").prefetch_related("mailing_lists").order_by("id"):
        email_key = _normalize_email(ar.email_address)
        if email_key and email_key in seen_emails:
            continue
        if email_key:
            seen_emails.add(email_key)
        validity, due_date, state = _effective_ar_validity(ar)
        authorized.append({
            "id": ar.id,
            "name": ar.authorized_name or "",
            "email": ar.email_address or "",
            "phone": ar.mobile_phone or "",
            "validity": validity,
            "due_date": _date_iso(due_date),
            "status": state,
        })

    supports = list(customer.support_groups.all())
    if site_filter:
        rack_ids = {r.id for r in racks}
        supports = [sg for sg in supports if sg.rack_id is None or sg.rack_id in rack_ids]

    return JsonResponse({
        "customer": {
            "id": customer.id,
            "name": customer.name_customer or "-",
            "office_phone": customer.office_phone or "",
            "status": _customer_status(customer),
            "total_authorized": len(authorized),
            "total_support": len(supports),
            "created_at": customer.created_at.isoformat() if customer.created_at else "",
        },
        "locations": [_rack_payload(r) for r in racks],
        "authorized_persons": authorized,
        "additional_mailing_lists": list(customer.additional_mailing_lists.order_by("email_address").values_list("email_address", flat=True)),
        "support_groups": [_support_payload(x) for x in supports],
        "associations": [_association_json(x) for x in customer.associations.all()],
    })

# ---------------------------------------------------------------------
# v1.8 CUSTOMER PROFILE CRUD (Customer + many Locations + customer-wide ARs)
# ---------------------------------------------------------------------
def _profile_location_from_payload(item):
    site = _get_site({"customer_site": item.get("customer_site") or item.get("site")})
    floor_payload = {
        "floor_level": item.get("floor_level") or item.get("floor_id"),
        "floor_name": item.get("floor_name") or item.get("floor"),
    }
    floor, _ = _resolve_or_create_floor(site, floor_payload)
    rack_payload = {
        "rack_id": item.get("rack_id"),
        "rack_name": item.get("rack_name") or item.get("rack_location") or item.get("rack"),
    }
    rack, _ = _resolve_or_create_rack(floor, rack_payload)
    return rack


def _profile_ar_status_value(due_date):
    if due_date and due_date < timezone.localdate():
        return ARGroup.VALIDITY_EXPIRED
    return ARGroup.VALIDITY_VALID


def _customer_profile_payload(customer):
    locations = []
    for rack in customer.racks.select_related("floor_level__site_location").order_by("floor_level__site_location__name", "floor_level__name", "name_racks"):
        locations.append({
            "rack_id": rack.id,
            "customer_site": rack.floor_level.site_location.name,
            "site_id": rack.floor_level.site_location_id,
            "floor_id": rack.floor_level_id,
            "floor_name": rack.floor_level.name,
            "rack_name": rack.name_racks,
        })

    ars = []
    seen = set()
    for ar in customer.ars.select_related("ar_group").prefetch_related("mailing_lists").order_by("id"):
        key = _normalize_email(ar.email_address)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        validity, due_date, state = _effective_ar_validity(ar)
        ars.append({
            "id": ar.id,
            "authorized_name": ar.authorized_name or "",
            "email": ar.email_address or "",
            "phone": ar.mobile_phone or "",
            "due_date": _date_iso(due_date),
            "validity": validity,
            "status": state,
        })
    additional_mailing_lists = list(
        customer.additional_mailing_lists.order_by("email_address").values_list("email_address", flat=True)
    )
    return {
        "customer_id": customer.id,
        "customer_name": customer.name_customer or "",
        "office_phone": customer.office_phone or "",
        "locations": locations,
        "ars": ars,
        "additional_mailing_lists": additional_mailing_lists,
    }


def _save_customer_profile(request, customer=None):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Payload JSON tidak valid."}, status=400)

    name = _norm_customer_name(payload.get("customer_name"))
    office_phone = _norm(payload.get("office_phone"))
    locations = payload.get("locations") or []
    ars_payload = payload.get("ars") or []
    additional_mailing_payload = payload.get("additional_mailing_lists") or []
    if not name:
        return JsonResponse({"detail": "Customer Name wajib diisi."}, status=400)
    if not isinstance(locations, list) or not locations:
        return JsonResponse({"detail": "Minimal 1 Location / Rack wajib ditambahkan."}, status=400)
    ok, err = _validate_unique_authorized_emails(ars_payload)
    if not ok:
        return JsonResponse({"detail": err}, status=400)

    duplicate = Customers.objects.filter(name_customer__iexact=name)
    if customer:
        duplicate = duplicate.exclude(id=customer.id)
    if duplicate.exists():
        return JsonResponse({"detail": "Customer dengan nama tersebut sudah terdaftar."}, status=409)

    try:
        with transaction.atomic():
            created = customer is None
            if customer is None:
                customer = Customers.objects.create(name_customer=name, office_phone=office_phone, created_by=request.user)
            else:
                customer.name_customer = name
                customer.office_phone = office_phone
                customer.save(update_fields=["name_customer", "office_phone", "updated_at"])

            racks = []
            seen_racks = set()
            for idx, item in enumerate(locations, start=1):
                rack = _profile_location_from_payload(item)
                if rack.id in seen_racks:
                    continue
                seen_racks.add(rack.id)
                racks.append(rack)
            customer.racks.set(racks)

            # Compatibility container only. AR ownership is customer-wide from v1.8.
            global_group = ARGroup.objects.filter(customer=customer, rack__isnull=True).order_by("id").first()
            if not global_group:
                global_group = ARGroup.objects.create(customer=customer, rack=None, validity_AR=ARGroup.VALIDITY_VALID, due_date=None)

            # Rebuild customer-wide Authorized Persons from the form. This also consolidates
            # legacy duplicate ARs that were previously repeated for each rack.
            AR.objects.filter(customer=customer).delete()
            for idx, item in enumerate(ars_payload, start=1):
                email = _normalize_email(item.get("email"))
                auth_name = _norm(item.get("authorized_name"))
                phone = _norm(item.get("phone"))
                if not email and not auth_name and not phone:
                    continue
                if not email:
                    raise ValueError(f"Email wajib diisi untuk Authorized Person #{idx}.")
                try:
                    validate_email(email)
                except ValidationError:
                    raise ValueError(f"Email Authorized Person #{idx} tidak valid.")
                due_date = _parse_date(item.get("due_date") or item.get("date"))
                validity = _profile_ar_status_value(due_date)
                ar = AR.objects.create(
                    customer=customer,
                    ar_group=global_group,
                    email_address=email,
                    authorized_name=auth_name,
                    mobile_phone=phone,
                    validity=validity,
                    due_date=due_date,
                )

            _sync_customer_additional_mailing_lists(customer, additional_mailing_payload)

            # Remove obsolete empty location-scoped AR groups created by the old UI.
            ARGroup.objects.filter(customer=customer, ars__isnull=True).exclude(id=global_group.id).delete()

            _record_activity(
                user=request.user,
                action="create" if created else "update",
                entity_type="Customer",
                entity_id=customer.id,
                entity_label=customer.name_customer,
                description=("Created" if created else "Updated") + f" customer profile {customer.name_customer}",
                metadata={"locations": len(racks), "authorized_persons": len(ars_payload), "additional_mailing_lists": len(_parse_additional_mailing_list_values(additional_mailing_payload))},
            )
            return JsonResponse({"status": "created" if created else "updated", "customer_id": customer.id})
    except (ValueError, ValidationError, IntegrityError) as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    except Exception as exc:
        logger.error("[Customer Profile] save failed: %s", exc, exc_info=True)
        return JsonResponse({"detail": "Internal server error"}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_protect
def customer_profile_create_api(request):
    return _save_customer_profile(request)


@login_required
@require_http_methods(["GET", "PUT"])
@csrf_protect
def customer_profile_api(request, customer_id):
    customer = get_object_or_404(Customers, id=customer_id)
    if request.method == "GET":
        return JsonResponse(_customer_profile_payload(customer))
    return _save_customer_profile(request, customer=customer)

def _parse_support_payload(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Payload JSON tidak valid.")
    name = _norm(payload.get("name"))
    if not name:
        raise ValueError("Nama support group wajib diisi.")
    rack_id = payload.get("rack_id") or None
    validity_raw = _norm(payload.get("validity_date"))
    validity_date = None
    if validity_raw:
        try:
            validity_date = datetime.strptime(validity_raw, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Validity harus berformat YYYY-MM-DD.")
    # v1.9.7: status is automatic from validity_date; ignore a manually supplied status.
    if validity_date:
        days = (validity_date - timezone.localdate()).days
        status = SupportGroup.STATUS_EXPIRED if days < 0 else (SupportGroup.STATUS_EXPIRING if days <= 30 else SupportGroup.STATUS_ACTIVE)
    else:
        status = SupportGroup.STATUS_ACTIVE
    return {
        "rack_id": rack_id,
        "name": name,
        "identity_number": _norm(payload.get("identity_number")),
        "access_level": _norm(payload.get("access_level")),
        "email_phone": _norm(payload.get("email_phone")),
        "reference_info": _norm(payload.get("reference_info")),
        "notes": _norm(payload.get("notes")),
        "validity_date": validity_date,
        "status": status,
    }


SUPPORT_GROUP_CSV_HEADERS = [
    "name", "identity_number", "access_level", "email_phone",
    "reference_info", "notes", "site", "floor", "rack",
    "validity_date", "status",
]


def _support_csv_status(raw_status, validity_date):
    # Status is derived from the date. raw_status remains accepted only for CSV backward compatibility.
    if validity_date:
        days = (validity_date - timezone.localdate()).days
        return SupportGroup.STATUS_EXPIRED if days < 0 else (SupportGroup.STATUS_EXPIRING if days <= 30 else SupportGroup.STATUS_ACTIVE)
    return SupportGroup.STATUS_ACTIVE


def _support_csv_rack(customer, site_name, floor_name, rack_name):
    site_name, floor_name, rack_name = map(_norm, (site_name, floor_name, rack_name))
    if not any((site_name, floor_name, rack_name)):
        return None
    if not all((site_name, floor_name, rack_name)):
        raise ValueError("Jika lokasi diisi, kolom site, floor, dan rack wajib lengkap.")
    rack = customer.racks.select_related("floor_level__site_location").filter(
        floor_level__site_location__name__iexact=site_name,
        floor_level__name__iexact=floor_name,
        name_racks__iexact=rack_name,
    ).first()
    if not rack:
        raise ValueError(f"Lokasi {site_name} / {floor_name} / {rack_name} tidak terdaftar pada customer ini.")
    return rack


@login_required
@require_http_methods(["GET"])
def support_groups_csv_template(request):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=SUPPORT_GROUP_CSV_HEADERS)
    writer.writeheader()
    writer.writerow({
        "name": "Engineer Example",
        "identity_number": "A12345678",
        "access_level": "Escort / Temporary",
        "email_phone": "engineer@example.com / 081234567890",
        "reference_info": "CAR-EXAMPLE-001",
        "notes": "Example support personnel",
        "site": "JKT2",
        "floor": "Level 1",
        "rack": "RACK-A01",
        "validity_date": (timezone.localdate() + timedelta(days=90)).isoformat(),
        "status": "Active",
    })
    response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="mailgenix_support_group_import_template.csv"'
    return response


@login_required
@require_http_methods(["POST"])
@csrf_protect
def customer_support_groups_csv_import(request, customer_id):
    forbidden = _require_admin(request.user)
    if forbidden:
        return forbidden
    customer = get_object_or_404(Customers, id=customer_id)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"detail": "Pilih file CSV Support Group terlebih dahulu."}, status=400)
    if not upload.name.lower().endswith(".csv"):
        return JsonResponse({"detail": "File harus berformat .csv"}, status=400)
    if upload.size > 5 * 1024 * 1024:
        return JsonResponse({"detail": "Ukuran CSV maksimal 5 MB."}, status=400)
    try:
        csv_text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return JsonResponse({"detail": "CSV harus menggunakan encoding UTF-8."}, status=400)
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return JsonResponse({"detail": "CSV tidak memiliki header."}, status=400)
    header_map = {h: _csv_boolish_text(h).lower() for h in reader.fieldnames}
    normalized = set(header_map.values())
    missing = [h for h in SUPPORT_GROUP_CSV_HEADERS if h not in normalized]
    if missing:
        return JsonResponse({"detail": "Header CSV Support Group tidak lengkap.", "missing_headers": missing}, status=400)

    created = updated = 0
    errors = []
    processed = 0
    for line_no, raw in enumerate(reader, start=2):
        row = {header_map.get(k, k): (v or "") for k, v in raw.items()}
        if not any(_norm(v) for v in row.values()):
            continue
        processed += 1
        try:
            name = _norm(row.get("name"))
            if not name:
                raise ValueError("Name wajib diisi.")
            validity_raw = _norm(row.get("validity_date"))
            validity_date = None
            if validity_raw:
                try:
                    validity_date = datetime.strptime(validity_raw, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("validity_date harus berformat YYYY-MM-DD.")
            rack = _support_csv_rack(customer, row.get("site"), row.get("floor"), row.get("rack"))
            status = _support_csv_status(row.get("status"), validity_date)
            identity_number = _norm(row.get("identity_number"))
            email_phone = _norm(row.get("email_phone"))
            lookup = {
                "customer": customer,
                "name": name,
                "identity_number": identity_number,
                "email_phone": email_phone,
                "rack": rack,
            }
            defaults = {
                "access_level": _norm(row.get("access_level")),
                "reference_info": _norm(row.get("reference_info")),
                "notes": _norm(row.get("notes")),
                "validity_date": validity_date,
                "status": status,
            }
            with transaction.atomic():
                item, was_created = SupportGroup.objects.update_or_create(defaults=defaults, **lookup)
            created += int(was_created)
            updated += int(not was_created)
        except (ValueError, TypeError, ValidationError, IntegrityError) as exc:
            errors.append({"line": line_no, "error": str(exc)})
        except Exception as exc:
            logger.error("[Support Group CSV] line %s failed: %s", line_no, exc, exc_info=True)
            errors.append({"line": line_no, "error": "Internal error while importing this row."})

    _record_activity(
        user=request.user, action="import", entity_type="Support Group CSV", entity_id=customer.id,
        entity_label=customer.name_customer,
        description=f"Imported Support Group CSV for {customer.name_customer}: {created} created, {updated} updated, {len(errors)} failed",
        metadata={"customer_id": customer.id, "filename": upload.name, "rows_read": processed, "created": created, "updated": updated, "error_count": len(errors)},
        status="success" if not errors else "partial",
    )
    return JsonResponse({
        "status": "completed", "rows_read": processed, "created_count": created,
        "updated_count": updated, "error_count": len(errors), "errors": errors,
    })


@login_required
@require_http_methods(["GET", "POST"])
def customer_support_groups_api(request, customer_id):
    customer = get_object_or_404(Customers, id=customer_id)
    if request.method == "GET":
        rows = customer.support_groups.select_related("rack__floor_level__site_location").all()
        return JsonResponse({"support_groups": [_support_payload(x) for x in rows]})
    # v1.9.3: both Admin and normal authenticated User roles can manage Support Group.
    try:
        data = _parse_support_payload(request)
        rack = None
        if data.pop("rack_id", None):
            rack = get_object_or_404(customer.racks.all(), id=int(json.loads(request.body.decode("utf-8")).get("rack_id")))
        item = SupportGroup.objects.create(customer=customer, rack=rack, **data)
        _record_activity(user=request.user, action="create", entity_type="Support Group", entity_id=item.id, entity_label=item.name,
                         description=f"Added Support Group - {item.name}",
                         metadata={"customer": customer.name_customer, "customer_id": customer.id, "rack_id": item.rack_id})
        return JsonResponse({"support_group": _support_payload(item)}, status=201)
    except (ValueError, TypeError) as exc:
        return JsonResponse({"detail": str(exc)}, status=400)


@login_required
@require_http_methods(["PUT", "DELETE"])
def support_group_detail_api(request, support_id):
    # v1.9.3: both Admin and normal authenticated User roles can edit/delete Support Group.
    item = get_object_or_404(SupportGroup, id=support_id)
    if request.method == "DELETE":
        label, customer_name, customer_id = item.name, item.customer.name_customer, item.customer_id
        item.delete()
        _record_activity(user=request.user, action="delete", entity_type="Support Group", entity_id=support_id, entity_label=label,
                         description=f"Deleted Support Group - {label}", metadata={"customer": customer_name, "customer_id": customer_id})
        return JsonResponse({"status": "deleted"})
    try:
        raw = json.loads(request.body.decode("utf-8") or "{}")
        data = _parse_support_payload(request)
        rack_id = data.pop("rack_id", None)
        if rack_id:
            item.rack = get_object_or_404(item.customer.racks.all(), id=int(rack_id))
        else:
            item.rack = None
        for key, value in data.items():
            setattr(item, key, value)
        item.save()
        _record_activity(user=request.user, action="update", entity_type="Support Group", entity_id=item.id, entity_label=item.name,
                         description=f"Updated Support Group - {item.name}", metadata={"customer": item.customer.name_customer, "customer_id": item.customer_id, "rack_id": item.rack_id})
        return JsonResponse({"support_group": _support_payload(item)})
    except (ValueError, TypeError) as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

# ---------------------------------------------------------------------
# SEQUENCE MANAGEMENT v1.9.6
# ---------------------------------------------------------------------
SEQUENCE_ROMAN_MONTHS = {1:"I",2:"II",3:"III",4:"IV",5:"V",6:"VI",7:"VII",8:"VIII",9:"IX",10:"X",11:"XI",12:"XII"}
SEQUENCE_SITE_CODES = {"JKT2":"2", "JKT 2":"2", "JKT02":"2", "JKT3":"3", "JKT 3":"3", "JKT03":"3"}


def _sequence_site_code(site):
    key = re.sub(r"\s+", " ", (site.name or "").strip().upper())
    if key in SEQUENCE_SITE_CODES:
        return SEQUENCE_SITE_CODES[key]
    compact = key.replace(" ", "")
    if compact in SEQUENCE_SITE_CODES:
        return SEQUENCE_SITE_CODES[compact]
    raise ValidationError("Sequence hanya mendukung site JKT2 dan JKT3.")


def _sequence_activity(sequence_type, raw):
    st = (sequence_type or "").strip().upper()
    value = (raw or "").strip().upper()
    valid_types = {x[0] for x in SequenceRecord.TYPE_CHOICES}
    if st not in valid_types:
        raise ValidationError("Sequence Type tidak valid.")
    if st == SequenceRecord.TYPE_EQM:
        if value not in {"IN", "OUT"}:
            raise ValidationError("Activity EQM harus IN atau OUT.")
        return value
    return st


def _sequence_json(record):
    return {
        "id": record.id,
        "sequence_number": record.sequence_number,
        "sequence_type": record.sequence_type,
        "activity": record.activity,
        "site_id": record.site_id,
        "site": record.site.name,
        "customer_id": record.customer_id,
        "customer": record.customer.name_customer or "-",
        "ticket_number": record.ticket_number,
        "document_status": record.document_status,
        "eqm_saved": record.eqm_saved,
        "operational_date": record.operational_date.isoformat(),
        "remarks": record.remarks,
        "status": record.status,
        "void_reason": record.void_reason,
        "approved_by": record.created_by.username if record.created_by else "-",
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _next_sequence_value(sequence_type, site, operational_date):
    """Allocate a monthly counter atomically. Number is never decremented/reused."""
    scope = {
        "sequence_type": sequence_type,
        "site": site,
        "year": operational_date.year,
        "month": operational_date.month,
    }
    for _ in range(3):
        try:
            with transaction.atomic():
                counter = SequenceCounter.objects.select_for_update().filter(**scope).first()
                if counter is None:
                    counter = SequenceCounter.objects.create(**scope, last_value=0)
                counter.last_value += 1
                counter.save(update_fields=["last_value", "updated_at"])
                return counter.last_value
        except IntegrityError:
            continue
    raise ValidationError("Gagal mengalokasikan nomor sequence. Silakan coba lagi.")


def _sequence_candidate(sequence_type, site, operational_date):
    current = SequenceCounter.objects.filter(
        sequence_type=sequence_type, site=site,
        year=operational_date.year, month=operational_date.month,
    ).values_list("last_value", flat=True).first() or 0
    return current + 1


def _format_sequence_number(sequence_type, site, counter_value, operational_date):
    site_code = _sequence_site_code(site)
    month = SEQUENCE_ROMAN_MONTHS[operational_date.month]
    return f"{sequence_type}/{site_code}-{counter_value:03d}/{month}/{operational_date.year}"


def _sequence_parse_date(raw):
    try:
        return datetime.strptime(str(raw or ""), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("Operational Date wajib diisi dengan format YYYY-MM-DD.")


def _sequence_payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("Payload JSON tidak valid.")


@login_required
@require_http_methods(["GET", "POST"])
def sequences_api(request):
    if request.method == "GET":
        qs = SequenceRecord.objects.select_related("site", "customer", "created_by").all()
        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(sequence_number__icontains=q) | Q(customer__name_customer__icontains=q) | Q(ticket_number__icontains=q))
        for param, field in (("type","sequence_type"),("status","status"),("document_status","document_status")):
            val = (request.GET.get(param) or "").strip()
            if val:
                qs = qs.filter(**{field: val})
        site = (request.GET.get("site") or "").strip()
        if site:
            qs = qs.filter(site__name__iexact=site)
        activity = (request.GET.get("activity") or "").strip()
        if activity:
            qs = qs.filter(activity=activity)
        month = request.GET.get("month")
        year = request.GET.get("year")
        if month and str(month).isdigit(): qs = qs.filter(operational_date__month=int(month))
        if year and str(year).isdigit(): qs = qs.filter(operational_date__year=int(year))

        this_month = timezone.localdate()
        month_qs = SequenceRecord.objects.filter(operational_date__year=this_month.year, operational_date__month=this_month.month)
        summary = {"total": month_qs.count()}
        known_total = 0
        for code, _ in SequenceRecord.TYPE_CHOICES:
            count = month_qs.filter(sequence_type=code).count()
            summary[code] = count
            known_total += count
        summary["other"] = max(summary["total"] - known_total, 0)
        return JsonResponse({"ok": True, "items": [_sequence_json(x) for x in qs[:1000]], "summary": summary})

    try:
        data = _sequence_payload(request)
        sequence_type = (data.get("sequence_type") or "").strip().upper()
        operational_date = _sequence_parse_date(data.get("operational_date"))
        site = get_object_or_404(SiteLocation, pk=int(data.get("site_id")))
        _sequence_site_code(site)
        customer = get_object_or_404(Customers, pk=int(data.get("customer_id")))
        if not customer.racks.filter(floor_level__site_location=site).exists():
            raise ValidationError("Customer tidak terdaftar pada site yang dipilih.")
        activity = _sequence_activity(sequence_type, data.get("activity"))
        doc_status = (data.get("document_status") or SequenceRecord.DOC_LINKED).strip()
        valid_doc = {x[0] for x in SequenceRecord.DOCUMENT_STATUS_CHOICES}
        if doc_status not in valid_doc:
            raise ValidationError("Document Status tidak valid.")
        eqm_saved = data.get("eqm_saved") if sequence_type == SequenceRecord.TYPE_EQM else None
        if eqm_saved not in {True, False, None}:
            eqm_saved = None

        with transaction.atomic():
            counter_value = _next_sequence_value(sequence_type, site, operational_date)
            sequence_number = _format_sequence_number(sequence_type, site, counter_value, operational_date)
            record = SequenceRecord.objects.create(
                sequence_number=sequence_number,
                sequence_type=sequence_type,
                activity=activity,
                site=site,
                customer=customer,
                ticket_number=(data.get("ticket_number") or "").strip()[:120],
                document_status=doc_status,
                eqm_saved=eqm_saved,
                operational_date=operational_date,
                remarks=(data.get("remarks") or "").strip()[:255],
                created_by=request.user,
                updated_by=request.user,
            )
            SequenceAuditLog.objects.create(sequence=record, action="create", changed_by=request.user, new_value=sequence_number)
        _record_activity(user=request.user, action="create", entity_type="Sequence", entity_id=record.id, entity_label=record.sequence_number, description=f"Created sequence {record.sequence_number}", metadata={"site": site.name, "customer": customer.name_customer})
        return JsonResponse({"ok": True, "item": _sequence_json(record)}, status=201)
    except (ValidationError, ValueError, TypeError) as exc:
        msg = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"ok": False, "error": msg}, status=400)


@login_required
@require_http_methods(["GET", "PATCH"])
def sequence_detail_api(request, sequence_id):
    record = get_object_or_404(SequenceRecord.objects.select_related("site", "customer", "created_by"), pk=sequence_id)
    if request.method == "GET":
        return JsonResponse({"ok": True, "item": _sequence_json(record)})

    if record.status == SequenceRecord.STATUS_VOID:
        return JsonResponse({"ok": False, "error": "Sequence VOID tidak dapat diedit."}, status=400)
    try:
        data = _sequence_payload(request)
        editable = {
            "activity", "customer_id", "ticket_number", "document_status", "eqm_saved", "operational_date", "remarks"
        }
        changes = []
        if "activity" in data:
            new = _sequence_activity(record.sequence_type, data.get("activity"))
            if new != record.activity: changes.append(("activity", record.activity, new)); record.activity = new
        if "customer_id" in data:
            customer = get_object_or_404(Customers, pk=int(data.get("customer_id")))
            if not customer.racks.filter(floor_level__site_location=record.site).exists():
                raise ValidationError("Customer tidak terdaftar pada site sequence ini.")
            if customer.id != record.customer_id: changes.append(("customer", record.customer.name_customer, customer.name_customer)); record.customer = customer
        if "ticket_number" in data:
            new = (data.get("ticket_number") or "").strip()[:120]
            if new != record.ticket_number: changes.append(("ticket_number", record.ticket_number, new)); record.ticket_number = new
        if "document_status" in data:
            new = (data.get("document_status") or "").strip()
            if new not in {x[0] for x in SequenceRecord.DOCUMENT_STATUS_CHOICES}: raise ValidationError("Document Status tidak valid.")
            if new != record.document_status: changes.append(("document_status", record.document_status, new)); record.document_status = new
        if "eqm_saved" in data and record.sequence_type == SequenceRecord.TYPE_EQM:
            new = data.get("eqm_saved")
            if new not in {True, False, None}: new = None
            if new != record.eqm_saved: changes.append(("eqm_saved", record.eqm_saved, new)); record.eqm_saved = new
        if "operational_date" in data:
            new = _sequence_parse_date(data.get("operational_date"))
            if new != record.operational_date: changes.append(("operational_date", record.operational_date, new)); record.operational_date = new
        if "remarks" in data:
            new = (data.get("remarks") or "").strip()[:255]
            if new != record.remarks: changes.append(("remarks", record.remarks, new)); record.remarks = new
        record.updated_by = request.user
        with transaction.atomic():
            record.save()
            for field, old, new in changes:
                SequenceAuditLog.objects.create(sequence=record, action="update", field_changed=field, old_value=str(old or ""), new_value=str(new or ""), changed_by=request.user)
        if changes:
            _record_activity(user=request.user, action="update", entity_type="Sequence", entity_id=record.id, entity_label=record.sequence_number, description=f"Updated sequence {record.sequence_number}")
        return JsonResponse({"ok": True, "item": _sequence_json(record)})
    except (ValidationError, ValueError, TypeError) as exc:
        msg = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"ok": False, "error": msg}, status=400)


@login_required
@require_POST
def sequence_void_api(request, sequence_id):
    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "Admin only."}, status=403)
    record = get_object_or_404(SequenceRecord, pk=sequence_id)
    if record.status == SequenceRecord.STATUS_VOID:
        return JsonResponse({"ok": True, "item": _sequence_json(record)})
    try:
        data = _sequence_payload(request)
        reason = (data.get("reason") or "").strip()[:255]
        if not reason:
            raise ValidationError("Alasan VOID wajib diisi.")
        with transaction.atomic():
            old = record.status
            record.status = SequenceRecord.STATUS_VOID
            record.void_reason = reason
            record.updated_by = request.user
            record.save(update_fields=["status", "void_reason", "updated_by", "updated_at"])
            SequenceAuditLog.objects.create(sequence=record, action="void", field_changed="status", old_value=old, new_value=f"Void - {reason}", changed_by=request.user)
        _record_activity(user=request.user, action="update", entity_type="Sequence", entity_id=record.id, entity_label=record.sequence_number, description=f"Voided sequence {record.sequence_number}: {reason}")
        return JsonResponse({"ok": True, "item": _sequence_json(record)})
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": exc.messages[0]}, status=400)


@login_required
@require_http_methods(["GET"])
def sequence_preview_api(request):
    try:
        sequence_type = (request.GET.get("type") or "").strip().upper()
        _sequence_activity(sequence_type, request.GET.get("activity") or ("IN" if sequence_type == "EQM" else sequence_type))
        site = get_object_or_404(SiteLocation, pk=int(request.GET.get("site_id")))
        operational_date = _sequence_parse_date(request.GET.get("operational_date"))
        candidate = _sequence_candidate(sequence_type, site, operational_date)
        return JsonResponse({"ok": True, "preview": _format_sequence_number(sequence_type, site, candidate, operational_date), "note": "Nomor final dikonfirmasi saat Create Sequence."})
    except (ValidationError, ValueError, TypeError) as exc:
        msg = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return JsonResponse({"ok": False, "error": msg}, status=400)


@login_required
@require_http_methods(["GET"])
def sequence_customers_api(request):
    site_id = request.GET.get("site_id")
    q = (request.GET.get("q") or "").strip()
    qs = Customers.objects.all().order_by("name_customer")
    if site_id and str(site_id).isdigit():
        qs = qs.filter(racks__floor_level__site_location_id=int(site_id)).distinct()
    if q:
        qs = qs.filter(name_customer__icontains=q)
    return JsonResponse({"ok": True, "items": [{"id": c.id, "name": c.name_customer or "-"} for c in qs[:100]]})


@login_required
@require_http_methods(["GET"])
def sequence_live_state_api(request):
    latest = SequenceRecord.objects.order_by("-updated_at").values("id", "updated_at").first()
    return JsonResponse({"ok": True, "count": SequenceRecord.objects.count(), "latest_id": latest["id"] if latest else None, "latest_updated_at": latest["updated_at"].isoformat() if latest else None})

@login_required
@require_http_methods(["GET"])
def sequence_audit_api(request, sequence_id):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Admin only."}, status=403)
    record = get_object_or_404(SequenceRecord, pk=sequence_id)
    rows = record.audit_logs.select_related("changed_by").all()[:500]
    return JsonResponse({"results": [{
        "action": a.action,
        "field": a.field_changed,
        "old": a.old_value,
        "new": a.new_value,
        "changed_by": a.changed_by.username if a.changed_by else "System",
        "changed_at": a.changed_at.isoformat(),
    } for a in rows]})


def _filtered_sequences(request):
    qs = SequenceRecord.objects.select_related("site", "customer", "created_by").all()
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(sequence_number__icontains=q) | Q(ticket_number__icontains=q) | Q(customer__name_customer__icontains=q))
    seq_type = (request.GET.get("type") or "").strip().upper()
    if seq_type:
        qs = qs.filter(sequence_type=seq_type)
    site = (request.GET.get("site") or "").strip()
    if site:
        qs = qs.filter(site__name__iexact=site)
    year = (request.GET.get("year") or "").strip()
    if year.isdigit():
        qs = qs.filter(operational_date__year=int(year))
    month = (request.GET.get("month") or "").strip()
    if month.isdigit():
        qs = qs.filter(operational_date__month=int(month))
    doc = (request.GET.get("document_status") or "").strip()
    if doc:
        qs = qs.filter(document_status=doc)
    return qs


def _apply_period_filter(qs, request):
    period = (request.GET.get("period") or "").lower()
    if period == "daily" and request.GET.get("date"):
        qs = qs.filter(operational_date=request.GET["date"])
    elif period in {"weekly", "custom"} and request.GET.get("start") and request.GET.get("end"):
        qs = qs.filter(operational_date__range=[request.GET["start"], request.GET["end"]])
    elif period == "monthly" and request.GET.get("year") and request.GET.get("month"):
        qs = qs.filter(operational_date__year=request.GET["year"], operational_date__month=request.GET["month"])
    elif period == "yearly" and request.GET.get("year"):
        qs = qs.filter(operational_date__year=request.GET["year"])
    return qs


def _xlsx_logo_path():
    candidates = [
        Path(settings.BASE_DIR) / "frontend/templates/static/email/ntt-data-logo.png",
        Path(settings.BASE_DIR) / "frontend/templates/static/email/ntt data logo email.png",
    ]
    return next((x for x in candidates if x.exists()), None)


def _excel_response(workbook, filename):
    buf = io.BytesIO(); workbook.save(buf); buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _style_report_sheet(ws, title, logo=True):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.drawing.image import Image as XLImage
    navy="073170"; light="D9E2F3"; white="FFFFFF"; border=Side(style="thin", color="A6A6A6")
    ws.sheet_view.showGridLines = False
    if logo and _xlsx_logo_path():
        try:
            img=XLImage(str(_xlsx_logo_path())); img.width=170; img.height=50; ws.add_image(img,"A1")
        except Exception:
            pass
    ws["D1"] = title; ws["D1"].font=Font(size=18,bold=True,color=navy); ws["D1"].alignment=Alignment(vertical="center")
    ws.row_dimensions[1].height=45
    return {"navy":navy,"light":light,"white":white,"border":border,"Font":Font,"PatternFill":PatternFill,"Alignment":Alignment,"Border":Border}


@login_required
def sequence_report_excel(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Admin only")
    from openpyxl import Workbook
    qs = _apply_period_filter(_filtered_sequences(request), request)
    wb=Workbook(); summary=wb.active; summary.title="Summary"; st=_style_report_sheet(summary,"SEQUENCE MANAGEMENT REPORT")
    period=(request.GET.get("period") or "custom").title(); site=(request.GET.get("site") or "ALL").upper()
    meta=[("Report Period",period),("Site",site),("Generated By",request.user.username),("Generated At",timezone.localtime().strftime("%d %B %Y %H:%M WIB")),("Total Sequence",qs.count())]
    r=4
    for k,v in meta:
        summary.cell(r,1,k).font=st["Font"](bold=True); summary.cell(r,2,v); r+=1
    r+=1; summary.cell(r,1,"SUMMARY BY TYPE").font=st["Font"](bold=True,color=st["white"]); summary.cell(r,1).fill=st["PatternFill"]("solid",fgColor=st["navy"]); summary.merge_cells(start_row=r,start_column=1,end_row=r,end_column=2); r+=1
    for t,_ in SequenceRecord.TYPE_CHOICES:
        summary.cell(r,1,t); summary.cell(r,2,qs.filter(sequence_type=t).count()); r+=1
    detail=wb.create_sheet("Detail Sequence"); st2=_style_report_sheet(detail,"DETAIL SEQUENCE")
    headers=["No","Sequence Number","Type","Activity","Customer Name","Site","Ticket Number","Document Status","EQM Saved","Operational Date","Approved By","Status","Remarks"]
    hr=4
    for c,h in enumerate(headers,1):
        cell=detail.cell(hr,c,h); cell.font=st2["Font"](bold=True,color=st2["white"]); cell.fill=st2["PatternFill"]("solid",fgColor=st2["navy"]); cell.alignment=st2["Alignment"](horizontal="center")
    count=0
    for idx,obj in enumerate(qs,1):
        count=idx
        vals=[idx,obj.sequence_number,obj.sequence_type,obj.activity,obj.customer.name_customer if obj.customer else "",obj.site.name,obj.ticket_number,obj.document_status,"Yes" if obj.eqm_saved else ("No" if obj.eqm_saved is False else "-"),obj.operational_date.strftime("%d/%m/%Y"),obj.created_by.username if obj.created_by else "-",obj.status,obj.remarks]
        for c,v in enumerate(vals,1): detail.cell(hr+idx,c,v)
    detail.freeze_panes="A5"; detail.auto_filter.ref=f"A4:M{max(4,4+count)}"
    widths=[6,28,10,12,34,9,20,28,12,18,18,12,40]
    from openpyxl.utils import get_column_letter
    for i,w in enumerate(widths,1): detail.column_dimensions[get_column_letter(i)].width=w
    pkey=(request.GET.get("period") or "").lower()
    if pkey=="daily" and request.GET.get("date"):
        token=request.GET["date"].replace("-","")
    elif pkey in {"weekly","custom"} and request.GET.get("start") and request.GET.get("end"):
        token=f'{request.GET["start"].replace("-","")}-{request.GET["end"].replace("-","")}'
    elif pkey=="monthly" and request.GET.get("year") and request.GET.get("month"):
        token=f'{int(request.GET["year"]):04d}{int(request.GET["month"]):02d}'
    elif pkey=="yearly" and request.GET.get("year"):
        token=str(request.GET["year"])
    else:
        token=timezone.localdate().strftime("%Y%m%d")
    filename=f'{site}_Sequence_Report_{period.replace(" ","")}_{token}.xlsx'
    return _excel_response(wb,filename)


# =====================================================================
# v1.9.7 CHECKLISTS / COMPLIANCE
# =====================================================================
def _checklist_submission_serialize(x):
    return {'id':x.id,'definition_id':x.definition_id,'definition':x.definition.name,'site':x.site,'operational_date':x.operational_date.isoformat(),'shift':x.shift,'pic':x.pic.username,'status':x.status,'answers':x.answers,'is_backdated':x.is_backdated,'created_at':x.created_at.isoformat()}


@login_required
@require_http_methods(['GET','POST'])
def checklists_api(request):
    if request.method=='GET':
        site=(request.GET.get('site') or '').upper(); qs=ChecklistDefinition.objects.filter(active=True)
        if site: qs=qs.filter(site=site)
        return JsonResponse({'definitions':[{'id':d.id,'code':d.code,'name':d.name,'site':d.site,'category':d.category,'schedule':d.schedule_config,'items':d.items} for d in qs]})

    payload=request.POST
    definition=get_object_or_404(ChecklistDefinition,pk=payload.get('definition_id'),active=True)
    date_raw=payload.get('operational_date') or timezone.localdate().isoformat()
    try:
        op_date=datetime.strptime(date_raw,'%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'detail':'Tanggal tidak valid.'},status=400)
    today=timezone.localdate()
    if op_date < today and not _is_admin(request.user):
        return JsonResponse({'detail':'User hanya dapat membuat checklist untuk hari ini. Backdate hanya Admin.'},status=403)
    if op_date > today:
        return JsonResponse({'detail':'Tanggal masa depan tidak diperbolehkan.'},status=400)

    shift=(payload.get('shift') or '').strip()
    answers_raw=payload.get('answers') or '{}'
    try:
        answers=json.loads(answers_raw) if isinstance(answers_raw,str) else answers_raw
    except Exception:
        return JsonResponse({'detail':'Jawaban checklist tidak valid.'},status=400)
    if not isinstance(answers,dict):
        return JsonResponse({'detail':'Jawaban checklist tidak valid.'},status=400)

    # Checklist-specific validation.
    if definition.code=='jkt2-mizuho-daily':
        if shift not in {'A3','B1'}:
            return JsonResponse({'detail':'Mizuho Daily Checklist hanya menggunakan Shift A3 atau B1.'},status=400)
        lamp_condition=answers.get('lamp_condition') or answers.get('lamp')
        lamp_remarks=answers.get('lamp_remarks') or answers.get('remarks')
        lamp_next=answers.get('lamp_next_action') or answers.get('next_action')
        if lamp_condition=='Not Good' and (not str(lamp_remarks or '').strip() or not str(lamp_next or '').strip()):
            return JsonResponse({'detail':'Remarks dan Next Action wajib jika kondisi LAMP = Not Good.'},status=400)
    elif definition.code.startswith('jkt2-bond-'):
        schedule=(definition.schedule_config or {}).get('shifts',{}).get(shift,[])
        if not schedule:
            return JsonResponse({'detail':'Schedule PATROL BOND untuk shift ini belum tersedia.'},status=400)
        missing_results=[t for t in schedule if not str(answers.get('result_'+t.replace(':','_')) or '').strip()]
        if missing_results:
            return JsonResponse({'detail':'Result wajib diisi untuk seluruh schedule: '+', '.join(missing_results)},status=400)
        if definition.code=='jkt2-bond-in-person':
            missing_evidence=[]
            for t in schedule:
                key='evidence_'+t.replace(':','_')
                if not request.FILES.getlist(key):
                    missing_evidence.append(t)
            if missing_evidence:
                return JsonResponse({'detail':'Evidence foto / screenshot Access Log wajib untuk: '+', '.join(missing_evidence)},status=400)

    status=payload.get('status') or ChecklistSubmission.STATUS_COMPLETED
    try:
        with transaction.atomic():
            obj=ChecklistSubmission.objects.create(
                definition=definition,operational_date=op_date,shift=shift,pic=request.user,
                site=definition.site,status=status,answers=answers,is_backdated=op_date<today,
                completed_at=timezone.now() if status==ChecklistSubmission.STATUS_COMPLETED else None,
            )
            for key in request.FILES:
                if key == 'evidence':
                    for f in request.FILES.getlist(key):
                        ChecklistEvidence.objects.create(submission=obj,file=f,uploaded_by=request.user,schedule_time=(payload.get('evidence_time') or ''))
                elif key.startswith('evidence_'):
                    schedule_time = key.replace('evidence_', '').replace('_', ':')
                    for f in request.FILES.getlist(key):
                        ChecklistEvidence.objects.create(submission=obj,file=f,uploaded_by=request.user,schedule_time=schedule_time)
    except IntegrityError:
        return JsonResponse({'detail':'Checklist untuk tanggal dan shift tersebut sudah ada.'},status=409)
    _record_activity(user=request.user,action='create',entity_type='Checklist',entity_id=obj.id,entity_label=definition.name,description=f'Checklist {definition.name} {op_date} {shift}',metadata={'backdated':obj.is_backdated,'site':obj.site})
    return JsonResponse(_checklist_submission_serialize(obj),status=201)


@login_required
@require_http_methods(['GET'])
def checklist_history_api(request):
    qs=ChecklistSubmission.objects.select_related('definition','pic').all()
    if request.GET.get('definition_id'): qs=qs.filter(definition_id=request.GET['definition_id'])
    if request.GET.get('site'): qs=qs.filter(site=request.GET['site'])
    if request.GET.get('year'): qs=qs.filter(operational_date__year=request.GET['year'])
    if request.GET.get('month'): qs=qs.filter(operational_date__month=request.GET['month'])
    return JsonResponse({'results':[_checklist_submission_serialize(x) for x in qs[:1000]]})


def _required_days_for_period(year, month):
    """Count only elapsed operational days; future days must not be reported as missed."""
    today=timezone.localdate()
    if (year,month) > (today.year,today.month):
        return 0
    if (year,month) == (today.year,today.month):
        return today.day
    return calendar.monthrange(year,month)[1]


def _required_slots_for_definition(defn, year, month):
    days=_required_days_for_period(year,month)
    if defn.code=='jkt2-mizuho-daily': return days*2
    # PATROL BOND totals across the applicable weekday/weekend shifts.
    # Video = 6 scheduled executions / operational day; In Person = 3 / day.
    if defn.code=='jkt2-bond-video': return days*6
    if defn.code=='jkt2-bond-in-person': return days*3
    return days


def _completed_slots_for_submission(sub):
    if sub.definition.code.startswith('jkt2-bond-'):
        schedule=(sub.definition.schedule_config or {}).get('shifts',{}).get(sub.shift,[])
        answers=sub.answers or {}
        return sum(1 for t in schedule if answers.get('result_'+t.replace(':','_')))
    return 1 if sub.status=='Completed' else 0


def _checklist_compliance_row(defn, year, month):
    subs=defn.submissions.filter(operational_date__year=year,operational_date__month=month).select_related('definition')
    required=_required_slots_for_definition(defn,year,month)
    if defn.code.startswith('jkt2-bond-'):
        completed=sum(_completed_slots_for_submission(x) for x in subs if x.status=='Completed')
        incomplete=sum(_completed_slots_for_submission(x) for x in subs if x.status=='Incomplete')
    elif defn.code=='jkt2-mizuho-daily':
        completed=subs.filter(status='Completed').count()
        incomplete=subs.filter(status='Incomplete').count()
    else:
        # Daily generic checklist counts a day once, even if legacy duplicate rows exist.
        completed=subs.filter(status='Completed').values('operational_date').distinct().count()
        incomplete=subs.filter(status='Incomplete').exclude(operational_date__in=subs.filter(status='Completed').values('operational_date')).values('operational_date').distinct().count()
    completed=min(completed,required) if required else 0
    incomplete=min(incomplete,max(required-completed,0)) if required else 0
    missed=max(required-completed-incomplete,0)
    return {'definition_id':defn.id,'name':defn.name,'required':required,'completed':completed,'incomplete':incomplete,'missed':missed,'compliance':round((completed/required*100) if required else 0,1)}


@login_required
def checklist_compliance_api(request):
    try:
        year=int(request.GET.get('year') or timezone.localdate().year); month=int(request.GET.get('month') or timezone.localdate().month)
    except ValueError:
        return JsonResponse({'detail':'Month/Year tidak valid.'},status=400)
    if month < 1 or month > 12:
        return JsonResponse({'detail':'Month tidak valid.'},status=400)
    qs=ChecklistDefinition.objects.filter(active=True)
    if request.GET.get('site'): qs=qs.filter(site=request.GET['site'])
    rows=[_checklist_compliance_row(d,year,month) for d in qs]
    return JsonResponse({'year':year,'month':month,'results':rows})


@login_required
def checklist_report_excel(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden('Admin only')
    from openpyxl import Workbook
    qs=ChecklistSubmission.objects.select_related('definition','pic').all()
    if request.GET.get('site'): qs=qs.filter(site=request.GET['site'])
    if request.GET.get('definition_id'): qs=qs.filter(definition_id=request.GET['definition_id'])
    period=(request.GET.get('period') or 'monthly').lower()
    try:
        year=int(request.GET.get('year') or timezone.localdate().year); month=int(request.GET.get('month') or timezone.localdate().month)
    except ValueError:
        return JsonResponse({'detail':'Month/Year tidak valid.'},status=400)
    if period=='daily' and request.GET.get('date'):
        qs=qs.filter(operational_date=request.GET['date'])
    elif period=='monthly':
        qs=qs.filter(operational_date__year=year,operational_date__month=month)
    elif period=='yearly':
        qs=qs.filter(operational_date__year=year)

    wb=Workbook(); sm=wb.active; sm.title='Summary'; st=_style_report_sheet(sm,'CHECKLIST REPORT')
    site=(request.GET.get('site') or 'ALL').upper()
    defn=ChecklistDefinition.objects.filter(pk=request.GET.get('definition_id')).first() if request.GET.get('definition_id') else None
    completed=qs.filter(status='Completed').count(); incomplete=qs.filter(status='Incomplete').count()
    required=missed=None; compliance=None
    if defn and period=='monthly':
        c=_checklist_compliance_row(defn,year,month)
        required,completed,incomplete,missed,compliance=c['required'],c['completed'],c['incomplete'],c['missed'],c['compliance']
    meta=[('Checklist',defn.name if defn else 'All Checklists'),('Site',site),('Period',period.title()),('Generated By',request.user.username),('Generated At',timezone.localtime().strftime('%d %B %Y %H:%M WIB'))]
    if required is not None:
        meta += [('Required',required),('Completed',completed),('Missed',missed),('Incomplete',incomplete),('Compliance',f'{compliance}%')]
    else:
        meta += [('Completed',completed),('Incomplete',incomplete)]
    for r,(k,v) in enumerate(meta,4):
        sm.cell(r,1,k).font=st['Font'](bold=True); sm.cell(r,2,v)
    sm.column_dimensions['A'].width=24; sm.column_dimensions['B'].width=45

    dt=wb.create_sheet('Checklist Detail'); st2=_style_report_sheet(dt,'CHECKLIST DETAIL')
    headers=['No','Date','Shift','Site','Checklist','PIC / Engineer','Status','Backdated','Answers / Result']
    for c,h in enumerate(headers,1):
        cell=dt.cell(4,c,h); cell.font=st2['Font'](bold=True,color='FFFFFF'); cell.fill=st2['PatternFill']('solid',fgColor=st2['navy'])
    for i,x in enumerate(qs,1):
        vals=[i,x.operational_date.strftime('%d/%m/%Y'),x.shift,x.site,x.definition.name,x.pic.username,x.status,'Yes' if x.is_backdated else 'No',json.dumps(x.answers,ensure_ascii=False)]
        for c,v in enumerate(vals,1): dt.cell(4+i,c,v)
    widths=[6,14,10,9,42,22,15,12,70]
    from openpyxl.utils import get_column_letter
    for i,w in enumerate(widths,1): dt.column_dimensions[get_column_letter(i)].width=w
    dt.freeze_panes='A5'; dt.auto_filter.ref=f'A4:I{max(4,4+qs.count())}'
    token = request.GET.get('date','').replace('-','') if period=='daily' else (f'{year:04d}{month:02d}' if period=='monthly' else f'{year:04d}')
    checklist_token=re.sub(r'[^A-Za-z0-9]+','_',defn.name).strip('_') if defn else 'All_Checklists'
    return _excel_response(wb,f'{site}_{checklist_token}_{period.title()}_{token}.xlsx')

# =====================================================================
# v1.9.7 CUSTOMER ASSOCIATIONS (Contractor/WAF + Visitor/AVE)
# =====================================================================
def _association_json(x):
    return {'id':x.id,'customer_id':x.customer_id,'type':x.association_type,'type_label':x.get_association_type_display(),'rack_id':x.rack_id,'name':x.name,'identity_number':x.identity_number,'access_level':x.access_level,'email_phone':x.email_phone,'reference_info':x.reference_info,'notes':x.notes,'validity_date':x.validity_date.isoformat() if x.validity_date else None,'status':x.validity_status}

@login_required
@require_http_methods(['GET','POST'])
def customer_associations_api(request, customer_id):
    customer=get_object_or_404(Customers,pk=customer_id)
    if request.method=='GET': return JsonResponse({'results':[_association_json(x) for x in customer.associations.all()]})
    data=request.POST if request.content_type!='application/json' else json.loads(request.body or '{}')
    assoc_type=data.get('type')
    if assoc_type not in dict(CustomerAssociation.TYPE_CHOICES): return JsonResponse({'detail':'Association type tidak valid.'},status=400)
    validity=None
    if data.get('validity_date'):
        try: validity=datetime.strptime(data['validity_date'],'%Y-%m-%d').date()
        except ValueError: return JsonResponse({'detail':'Validity date tidak valid.'},status=400)
    obj=CustomerAssociation.objects.create(customer=customer,association_type=assoc_type,rack=Rack.objects.filter(pk=data.get('rack_id')).first() if data.get('rack_id') else None,name=(data.get('name') or '').strip(),identity_number=(data.get('identity_number') or '').strip(),access_level=(data.get('access_level') or '').strip(),email_phone=(data.get('email_phone') or '').strip(),reference_info=(data.get('reference_info') or '').strip(),notes=(data.get('notes') or '').strip(),validity_date=validity)
    _record_activity(user=request.user,action='create',entity_type='CustomerAssociation',entity_id=obj.id,entity_label=obj.name,description=f'Created {obj.get_association_type_display()} for {customer}')
    return JsonResponse(_association_json(obj),status=201)

@login_required
@require_http_methods(['PUT','DELETE'])
def customer_association_detail_api(request, association_id):
    obj=get_object_or_404(CustomerAssociation,pk=association_id)
    if request.method=='DELETE':
        label=obj.name; obj.delete(); _record_activity(user=request.user,action='delete',entity_type='CustomerAssociation',entity_id=association_id,entity_label=label,description=f'Deleted association {label}'); return JsonResponse({'ok':True})
    data=json.loads(request.body or '{}')
    for field in ['name','identity_number','access_level','email_phone','reference_info','notes']:
        if field in data: setattr(obj,field,(data.get(field) or '').strip())
    if data.get('type') in dict(CustomerAssociation.TYPE_CHOICES): obj.association_type=data.get('type')
    if 'rack_id' in data: obj.rack=Rack.objects.filter(pk=data.get('rack_id')).first() if data.get('rack_id') else None
    if 'validity_date' in data:
        try: obj.validity_date=datetime.strptime(data['validity_date'],'%Y-%m-%d').date() if data['validity_date'] else None
        except ValueError: return JsonResponse({'detail':'Validity date tidak valid.'},status=400)
    obj.save(); return JsonResponse(_association_json(obj))

# =====================================================================
# v1.9.7 REMOTE HANDS REPORT
# =====================================================================
def _rh_json(x):
    return {'id':x.id,'report_type':x.report_type,'ticket_number':x.ticket_number,'site':x.site,'start_datetime':x.start_datetime.isoformat(),'finish_datetime':x.finish_datetime.isoformat(),'engineer':x.engineer,'request_by':x.request_by,'shift_leader':x.shift_leader,'customer_id':x.customer_id,'customer_name':x.customer.name_customer,'rack_number':x.rack_number,'task_detail':x.task_detail,'result_information':x.result_information,'status':x.status,'created_by':x.created_by.username,'attachments':[{'id':a.id,'name':a.file.name.split('/')[-1],'caption':a.caption} for a in x.attachments.all()]}

@login_required
@require_http_methods(['GET','POST'])
def remote_hands_api(request):
    if request.method=='GET':
        qs=RemoteHandsReport.objects.select_related('customer','created_by').prefetch_related('attachments').all()[:200]
        return JsonResponse({'results':[_rh_json(x) for x in qs]})
    data=request.POST
    customer=get_object_or_404(Customers,pk=data.get('customer_id'))
    def parse_dt(v):
        if not v: return None
        dt=datetime.fromisoformat(v)
        if timezone.is_naive(dt): dt=timezone.make_aware(dt)
        return dt
    try:
        start=parse_dt(data.get('start_datetime')); finish=parse_dt(data.get('finish_datetime')); additional=parse_dt(data.get('additional_datetime'))
    except Exception:
        return JsonResponse({'detail':'Date & Time tidak valid.'},status=400)
    if not start or not finish: return JsonResponse({'detail':'Start dan Finish Date & Time wajib.'},status=400)
    obj=RemoteHandsReport.objects.create(report_type=data.get('report_type') or RemoteHandsReport.TYPE_REMOTE,ticket_number=(data.get('ticket_number') or '').strip(),site=(data.get('site') or '').strip(),start_datetime=start,finish_datetime=finish,additional_datetime=additional,engineer=(data.get('engineer') or request.user.username).strip(),request_by=(data.get('request_by') or '').strip(),shift_leader=(data.get('shift_leader') or '').strip(),customer=customer,rack_number=(data.get('rack_number') or '').strip(),task_detail=(data.get('task_detail') or '').strip(),result_information=(data.get('result_information') or '').strip(),status=data.get('status') or RemoteHandsReport.STATUS_DRAFT,created_by=request.user)
    for i,f in enumerate(request.FILES.getlist('attachments')):
        RemoteHandsAttachment.objects.create(report=obj,file=f,caption=(data.get(f'caption_{i}') or '').strip())
    _record_activity(user=request.user,action='create',entity_type='RemoteHandsReport',entity_id=obj.id,entity_label=obj.ticket_number,description=f'Created Remote Hands report {obj.ticket_number}',metadata={'site':obj.site})
    return JsonResponse(_rh_json(obj),status=201)


def _rh_filename(obj, ext):
    customer=re.sub(r'[^A-Za-z0-9]+','_',obj.customer.name_customer or 'Customer').strip('_')
    report_type='RemoteHands' if obj.report_type==RemoteHandsReport.TYPE_REMOTE else 'CustomRemoteHands'
    return f"{obj.site}_{re.sub(r'[^A-Za-z0-9_-]+','_',obj.ticket_number)}_{report_type}_{customer}_{timezone.localtime(obj.start_datetime).strftime('%Y%m%d')}.{ext}"

@login_required
def remote_hands_pdf(request, report_id):
    obj=get_object_or_404(RemoteHandsReport.objects.select_related('customer','created_by').prefetch_related('attachments'),pk=report_id)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
    except ImportError:
        return JsonResponse({'detail':'reportlab belum terinstall. Jalankan pip install -r requirements.txt'},status=500)
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm); styles=getSampleStyleSheet(); story=[]
    lp=_xlsx_logo_path()
    if lp: story.append(Image(str(lp),width=45*mm,height=13*mm)); story.append(Spacer(1,5*mm))
    story.append(Paragraph('<b>SERVICE REPORT - REMOTE HANDS</b>',styles['Title'])); story.append(Spacer(1,4*mm))
    def sec(title,rows):
        story.append(Table([[title]],colWidths=[180*mm],style=[('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#073170')),('TEXTCOLOR',(0,0),(-1,-1),colors.white),('ALIGN',(0,0),(-1,-1),'CENTER'),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('PADDING',(0,0),(-1,-1),6)]));
        t=Table([[k,Paragraph(str(v or '-').replace('\n','<br/>'),styles['BodyText'])] for k,v in rows],colWidths=[48*mm,132*mm]);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#d9d9d9')),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)]));story.append(t);story.append(Spacer(1,4*mm))
    sec('Inquiry Information',[('Type of Report',obj.report_type),('Ticket Number',obj.ticket_number),('Start Date & Time',timezone.localtime(obj.start_datetime).strftime('%d %B %Y %H:%M:%S [JKT TIME]')),('Finish Date & Time',timezone.localtime(obj.finish_datetime).strftime('%d %B %Y %H:%M:%S [JKT TIME]')),('Additional Date & Time',timezone.localtime(obj.additional_datetime).strftime('%d %B %Y %H:%M:%S') if obj.additional_datetime else '-'),('Engineer',obj.engineer),('Request By',obj.request_by),('Shift Leader',obj.shift_leader)])
    sec('Customer Information',[('Customer Name',obj.customer.name_customer),('Rack Number',obj.rack_number)])
    sec('Task Information',[('Task Detail',obj.task_detail)]); sec('Result Information',[('Result',obj.result_information)])
    if obj.attachments.exists():
        story.append(Table([['Attachments / Photos']],colWidths=[180*mm],style=[('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#073170')),('TEXTCOLOR',(0,0),(-1,-1),colors.white),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('PADDING',(0,0),(-1,-1),6)])); story.append(Spacer(1,3*mm))
        for idx,a in enumerate(obj.attachments.all(),1):
            try:
                if a.file and str(a.file.name).lower().endswith(('.png','.jpg','.jpeg','.webp')):
                    story.append(Image(a.file.path,width=150*mm,height=90*mm,kind='proportional'))
            except Exception:
                story.append(Paragraph(f'Attachment {idx}: {a.file.name}',styles['BodyText']))
            if a.caption: story.append(Paragraph(a.caption.replace('\n','<br/>'),styles['BodyText']))
            story.append(Spacer(1,4*mm))
    doc.build(story); buf.seek(0);resp=HttpResponse(buf.getvalue(),content_type='application/pdf');resp['Content-Disposition']=f'attachment; filename="{_rh_filename(obj,"pdf")}"';return resp

@login_required
def remote_hands_docx(request, report_id):
    obj=get_object_or_404(RemoteHandsReport.objects.select_related('customer','created_by').prefetch_related('attachments'),pk=report_id)
    try:
        from docx import Document
        from docx.shared import Inches
    except ImportError:
        return JsonResponse({'detail':'python-docx belum terinstall. Jalankan pip install -r requirements.txt'},status=500)
    doc=Document(); lp=_xlsx_logo_path()
    if lp: doc.add_picture(str(lp),width=Inches(2.2))
    doc.add_heading('SERVICE REPORT - REMOTE HANDS',0)
    def section(title,rows):
        doc.add_heading(title,level=1);t=doc.add_table(rows=0,cols=2);t.style='Table Grid'
        for k,v in rows: cells=t.add_row().cells;cells[0].text=str(k);cells[1].text=str(v or '-')
    section('Inquiry Information',[('Type of Report',obj.report_type),('Ticket Number',obj.ticket_number),('Start Date & Time',timezone.localtime(obj.start_datetime).strftime('%d %B %Y %H:%M:%S [JKT TIME]')),('Finish Date & Time',timezone.localtime(obj.finish_datetime).strftime('%d %B %Y %H:%M:%S [JKT TIME]')),('Engineer',obj.engineer),('Request By',obj.request_by),('Shift Leader',obj.shift_leader)])
    section('Customer Information',[('Customer Name',obj.customer.name_customer),('Rack Number',obj.rack_number)]);section('Task Information',[('Task Detail',obj.task_detail)]);section('Result Information',[('Result',obj.result_information)])
    if obj.attachments.exists():
        doc.add_heading('Attachments / Photos', level=1)
        for idx,a in enumerate(obj.attachments.all(),1):
            try:
                if a.file and str(a.file.name).lower().endswith(('.png','.jpg','.jpeg','.webp')): doc.add_picture(a.file.path, width=Inches(5.8))
                else: doc.add_paragraph(f'Attachment {idx}: {a.file.name}')
            except Exception:
                doc.add_paragraph(f'Attachment {idx}: {a.file.name}')
            if a.caption: doc.add_paragraph(a.caption)
    buf=io.BytesIO();doc.save(buf);buf.seek(0);resp=HttpResponse(buf.getvalue(),content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document');resp['Content-Disposition']=f'attachment; filename="{_rh_filename(obj,"docx")}"';return resp
