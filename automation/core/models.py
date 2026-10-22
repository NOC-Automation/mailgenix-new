# core/models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


# ==========================
#  User Manager
# ==========================
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("Username wajib diisi")

        username = self.model.normalize_username(username)

        # Normalisasi role ke {'admin', 'user'}
        role = (extra_fields.get("role") or "").strip().lower()
        if role not in {"admin", "user"}:
            role = "user"
        extra_fields["role"] = role

        user = self.model(username=username, **extra_fields)
        # Penting: gunakan API standar agar hash tersimpan benar ke kolom password_hash (via db_column)
        user.set_password(password)
        # Default flags jika tidak disuplai
        if "is_active" not in extra_fields:
            user.is_active = True
        if "is_staff" not in extra_fields:
            user.is_staff = (role == "admin") or extra_fields.get("is_staff", False)
        if "is_superuser" not in extra_fields:
            user.is_superuser = (role == "admin") or extra_fields.get("is_superuser", False)

        user.save(using=self._db)
        return user

    def create_user(self, username, password=None, **extra_fields):
        # Secara default, user biasa
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", "user")
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username, password=None, **extra_fields):
        # Superuser = admin penuh
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser harus memiliki is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser harus memiliki is_superuser=True.")

        return self._create_user(username, password, **extra_fields)


# ==========================
#  Custom User Model
# ==========================
class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User dengan 'role' yang distandardkan: {'admin', 'user'}.
    Menyimpan hash password di kolom DB 'password_hash' (bukan 'password') untuk kompatibilitas
    dengan skema yang sudah ada, menggunakan db_column pada field 'password'.
    """

    ROLE_ADMIN = "admin"
    ROLE_USER = "user"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Admin"),
        (ROLE_USER,  "User"),
    )

    # Identitas
    username = models.CharField(max_length=150, unique=True)

    # Simpan hash ke kolom 'password_hash' agar sesuai skema lama
    # Django tetap memakai field 'password' yang benar, hanya kolom DB-nya yang dialihkan.
    password = models.CharField(max_length=128, db_column="password_hash")

    # Otentikasi/otorisasi
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # RBAC
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        null=False,
        blank=False,
        help_text="Peran user: 'admin' atau 'user' (default: user).",
    )

    # Audit
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    # Manager
    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []  # tidak butuh field lain saat createsuperuser

    class Meta:
        # Jika kamu selama ini sudah memakai nama tabel khusus, set di sini:
        # db_table = 'accounts_user'
        ordering = ("-id",)

    # Normalisasi & guard untuk role
    def save(self, *args, **kwargs):
        if self.role:
            self.role = str(self.role).strip().lower()
            if self.role not in {self.ROLE_ADMIN, self.ROLE_USER}:
                self.role = self.ROLE_USER
        else:
            self.role = self.ROLE_USER
        super().save(*args, **kwargs)

    # Helper untuk pengecekan cepat di view/template
    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"


# ==========================
# Site Location
# ==========================
class SiteLocation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "site_locations"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ==========================
# Floor Level
# ==========================
class FloorLevel(models.Model):
    name = models.CharField(max_length=255)
    site_location = models.ForeignKey(
        SiteLocation,
        on_delete=models.CASCADE,
        related_name="floor_levels",
        db_column="site_location_id",
        null=False,
        blank=False,
    )

    rack_location = models.CharField(max_length=255, db_column='rack_location', null=True, blank=True)
    desc = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "floor_level"
        constraints = [
            models.UniqueConstraint(
                fields=["site_location", "name"],
                name="uniq_floor_name_per_site",
            )
        ]

    def __str__(self):
        return f"{self.name} @ {self.site_location.name}"


# ==========================
# Rack
# ==========================
class Rack(models.Model):
    floor_level = models.ForeignKey(
        FloorLevel,
        on_delete=models.CASCADE,
        related_name="racks",
        db_column="floor_level_id",
        null=False,
        blank=False,
    )
    name_racks = models.CharField(max_length=255, db_column='name_racks')

    class Meta:
        db_table = "racks"
        constraints = [
            models.UniqueConstraint(
                fields=["floor_level", "name_racks"],
                name="uniq_rack_name_per_floor",
            )
        ]

    def __str__(self):
        return self.name_racks


# ==========================
# Customer
# ==========================
class Customers(models.Model):
    authorized = models.CharField(max_length=255, db_column="Authorized", null=True, blank=True)
    name_customer = models.CharField(max_length=255, db_column='name_customer', null=True, blank=True)
    office_phone = models.CharField(max_length=50, db_column='office_phone', null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers_created",
        db_column="created_by",
    )

    # 🔑 CUSTOMER ⇄ RACK (M2M)
    racks = models.ManyToManyField(
        Rack,
        related_name="customers",
        db_table="customer_racks",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"

    def __str__(self):
        return self.name_customer or "-"


# ==========================
# AR Group
# ==========================
class ARGroup(models.Model):
    VALIDITY_EXPIRED = "Expired"
    VALIDITY_VALID = "Valid"

    VALIDITY_CHOICES = [
        (VALIDITY_EXPIRED, "Expired"),
        (VALIDITY_VALID, "Valid"),
    ]

    # 🔑 OWNER UTAMA
    customer = models.ForeignKey(
        Customers,
        on_delete=models.CASCADE,
        related_name="ar_groups",
        db_column="customer_id",
    )

    # Lokasi operasional AR Group. Satu customer dapat memiliki AR berbeda
    # pada rack/site/floor yang berbeda. Nullable untuk kompatibilitas data lama.
    rack = models.ForeignKey(
        Rack,
        on_delete=models.SET_NULL,
        related_name="ar_groups",
        db_column="rack_id",
        null=True,
        blank=True,
    )

    validity_AR = models.CharField(
        max_length=10,
        choices=VALIDITY_CHOICES,
        null=True,
        blank=True,
    )
    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ar_group"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "rack", "validity_AR", "due_date"],
                name="uniq_ar_group_per_customer_rack",
            )
        ]

    def __str__(self):
        return f"{self.customer} - {self.rack or 'No Rack'} - {self.validity_AR} (due {self.due_date})"


# ==========================
# Dynamic Mailing Group
# ==========================
class MailingGroup(models.Model):
    """Dynamic bulk-recipient grouping based on Site + selected Floors."""
    name = models.CharField(max_length=150, unique=True)
    site = models.ForeignKey(
        SiteLocation,
        on_delete=models.CASCADE,
        related_name="mailing_groups",
    )
    floors = models.ManyToManyField(
        FloorLevel,
        related_name="mailing_groups",
        blank=True,
    )
    specific_customers = models.ManyToManyField(
        Customers,
        related_name="explicit_mailing_groups",
        blank=True,
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mailing_groups"
        ordering = ["site__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.site})"


# ==========================
# Mailing List
# ==========================
class MailingList(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mailing_lists"

    def __str__(self):
        return self.name


# ==========================
# Customer Additional Mailing List
# ==========================
class CustomerAdditionalMailingList(models.Model):
    """Customer-level external mailing-list address used by the recipient resolver."""
    customer = models.ForeignKey(
        Customers,
        on_delete=models.CASCADE,
        related_name="additional_mailing_lists",
        db_column="customer_id",
    )
    email_address = models.EmailField(max_length=255)
    label = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_additional_mailing_lists"
        ordering = ["customer__name_customer", "email_address"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "email_address"],
                name="uniq_customer_additional_mailing_email",
            )
        ]

    def save(self, *args, **kwargs):
        self.email_address = (self.email_address or "").strip().lower()
        self.label = (self.label or "").strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email_address


# ==========================
# AR (Authorized Person)
# ==========================
class AR(models.Model):
    email_address = models.EmailField(max_length=255)
    authorized_name = models.CharField(max_length=255, null=True, blank=True)
    mobile_phone = models.CharField(max_length=50, null=True, blank=True)

    # 🔑 AR GROUP ADALAH OWNER LOGIS
    ar_group = models.ForeignKey(
        ARGroup,
        on_delete=models.CASCADE,
        related_name="ars",
        db_column="ar_group_id",
    )

    # (opsional tapi aman) direct customer guard
    customer = models.ForeignKey(
        Customers,
        on_delete=models.CASCADE,
        related_name="ars",
        db_column="customer_id",
        null=False,
        blank=False,
    )

    # 🔑 AR ⇄ MAILING LIST
    mailing_lists = models.ManyToManyField(
        MailingList,
        related_name="ars",
        db_table="ar_mailing_lists",
        blank=True,
    )

    # v1.8: validity belongs to the Authorized Person itself.
    # ARGroup is retained as a compatibility container for existing data,
    # but new customer-profile records are no longer location-scoped.
    validity = models.CharField(
        max_length=10,
        choices=ARGroup.VALIDITY_CHOICES,
        default=ARGroup.VALIDITY_VALID,
        null=True,
        blank=True,
    )
    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ar"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "ar_group", "email_address"],
                name="uniq_ar_email_per_customer_group",
            )
        ]
        indexes = [
            models.Index(fields=["email_address"]),
        ]

    def __str__(self):
        cust = self.customer.name_customer if self.customer else "-"
        email = self.email_address or "-"
        return f"{email} ({cust})"


# ==========================
# Support Group
# ==========================
class SupportGroup(models.Model):
    STATUS_ACTIVE = "Active"
    STATUS_EXPIRING = "Expiring Soon"
    STATUS_EXPIRED = "Expired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRING, "Expiring Soon"),
        (STATUS_EXPIRED, "Expired"),
    ]

    customer = models.ForeignKey(
        Customers,
        on_delete=models.CASCADE,
        related_name="support_groups",
        db_column="customer_id",
    )
    # Optional location scope. A support engineer can be registered for a
    # specific rack/site/floor while still being grouped under the customer.
    rack = models.ForeignKey(
        Rack,
        on_delete=models.SET_NULL,
        related_name="support_groups",
        db_column="rack_id",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255)
    identity_number = models.CharField(max_length=255, blank=True, default="")
    access_level = models.CharField(max_length=255, blank=True, default="")
    email_phone = models.CharField(max_length=255, blank=True, default="")
    reference_info = models.CharField(max_length=255, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")
    validity_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_groups"
        ordering = ["customer_id", "name", "id"]
        indexes = [
            models.Index(fields=["customer", "status"], name="support_gro_custome_75327c_idx"),
            models.Index(fields=["validity_date"], name="support_gro_validit_c82930_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.validity_date:
            days = (self.validity_date - timezone.localdate()).days
            self.status = self.STATUS_EXPIRED if days < 0 else (self.STATUS_EXPIRING if days <= 30 else self.STATUS_ACTIVE)
        else:
            self.status = self.STATUS_ACTIVE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.customer}"



# ==========================
# Activity Log (append-only audit trail)
# ==========================
class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("import", "Import"),
        ("generate_notification", "Generate Notification"),
        ("login", "Login"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, default="other")
    entity_type = models.CharField(max_length=80, blank=True, default="")
    entity_id = models.CharField(max_length=80, blank=True, default="")
    entity_label = models.CharField(max_length=255, blank=True, default="")
    description = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=30, default="success")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"], name="activity_lo_created_4db17e_idx"),
            models.Index(fields=["action"], name="activity_lo_action_c6533b_idx"),
            models.Index(fields=["entity_type"], name="activity_lo_entity__2bd630_idx"),
        ]

    def __str__(self):
        actor = self.user.username if self.user else "system"
        return f"{actor}: {self.action} {self.entity_type} {self.entity_label}"


# ==========================
# Application Changelog
# ==========================
class Changelog(models.Model):
    version = models.CharField(max_length=40)
    title = models.CharField(max_length=255, blank=True, default="")
    changes = models.JSONField(default=list, blank=True)
    released_at = models.DateField(default=timezone.localdate)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_changelog"
        ordering = ["-released_at", "-id"]

    def __str__(self):
        return f"{self.version} - {self.title or 'MailGenix update'}"

# ==========================
# Email Logs
# ==========================
class EmailLogs(models.Model):
    email_account = models.ForeignKey(
        AR,
        on_delete=models.CASCADE,
        related_name="email_logs",
        db_column="email_account_id",
        null=True,
        blank=True,
    )
    mailing_list = models.ForeignKey(
        MailingList,
        on_delete=models.CASCADE,
        related_name="email_logs",
        db_column="mailing_list_id",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customers,
        on_delete=models.CASCADE,
        related_name="email_logs",
        db_column="customer_id",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
        db_column="user_id",
    )

    subject = models.CharField(max_length=255)
    body = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_logs"
        ordering = ["-sent_at", "-id"]

    def __str__(self):
        return f"{self.subject} - {self.status or 'unknown'}"

# ==========================
# v1.9.7 Customer Associations
# ==========================
class CustomerAssociation(models.Model):
    TYPE_CONTRACTOR_WAF = "contractor_waf"
    TYPE_VISITOR_AVE = "visitor_ave"
    TYPE_CHOICES = [(TYPE_CONTRACTOR_WAF, "Contractor / WAF"), (TYPE_VISITOR_AVE, "Visitor / AVE")]

    customer = models.ForeignKey(Customers, on_delete=models.CASCADE, related_name="associations")
    association_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    rack = models.ForeignKey(Rack, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_associations")
    name = models.CharField(max_length=255)
    identity_number = models.CharField(max_length=255, blank=True, default="")
    access_level = models.CharField(max_length=255, blank=True, default="")
    email_phone = models.CharField(max_length=255, blank=True, default="")
    reference_info = models.CharField(max_length=255, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")
    validity_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_associations"
        ordering = ["customer_id", "association_type", "name"]

    @property
    def validity_status(self):
        if not self.validity_date:
            return "Active"
        days = (self.validity_date - timezone.localdate()).days
        if days < 0:
            return "Expired"
        if days <= 30:
            return "Expiring Soon"
        return "Active"


# ==========================
# Sequence Management (v1.9.6)
# ==========================
class SequenceCounter(models.Model):
    """Atomic monthly counter scoped by sequence type + site + year + month."""
    sequence_type = models.CharField(max_length=10)
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE, related_name="sequence_counters")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    last_value = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sequence_counters"
        constraints = [
            models.UniqueConstraint(
                fields=["sequence_type", "site", "year", "month"],
                name="uniq_sequence_counter_scope",
            )
        ]

    def __str__(self):
        return f"{self.sequence_type}/{self.site}/{self.month}/{self.year}: {self.last_value}"


class SequenceRecord(models.Model):
    TYPE_EQM = "EQM"
    TYPE_ESG = "ESG"
    TYPE_WAF = "WAF"
    TYPE_AVE = "AVE"
    TYPE_RTA = "RTA"
    TYPE_SFR = "SFR"
    TYPE_DAC = "DAC"
    TYPE_SAC = "SAC"
    TYPE_POC = "POC"
    TYPE_CHOICES = [(x, x) for x in (TYPE_EQM, TYPE_ESG, TYPE_WAF, TYPE_AVE, TYPE_RTA, TYPE_SFR, TYPE_DAC, TYPE_SAC, TYPE_POC)]

    DOC_LINKED = "Linked"
    DOC_PRINTED = "Printed"
    DOC_TENANT_LIST = "Tenant List"
    DOC_QR_TENANT = "QR Already Sent & Tenant List"
    DOCUMENT_STATUS_CHOICES = [
        (DOC_LINKED, DOC_LINKED),
        (DOC_PRINTED, DOC_PRINTED),
        (DOC_TENANT_LIST, DOC_TENANT_LIST),
        (DOC_QR_TENANT, DOC_QR_TENANT),
    ]

    STATUS_ACTIVE = "Active"
    STATUS_VOID = "Void"
    STATUS_CHOICES = [(STATUS_ACTIVE, STATUS_ACTIVE), (STATUS_VOID, STATUS_VOID)]

    sequence_number = models.CharField(max_length=80, unique=True, editable=False)
    sequence_type = models.CharField(max_length=10, choices=TYPE_CHOICES, editable=False)
    activity = models.CharField(max_length=40)
    site = models.ForeignKey(SiteLocation, on_delete=models.PROTECT, related_name="sequences")
    customer = models.ForeignKey(Customers, on_delete=models.PROTECT, related_name="sequences")
    ticket_number = models.CharField(max_length=120, blank=True, default="")
    document_status = models.CharField(max_length=60, choices=DOCUMENT_STATUS_CHOICES, default=DOC_LINKED)
    eqm_saved = models.BooleanField(null=True, blank=True)
    operational_date = models.DateField()
    remarks = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    void_reason = models.CharField(max_length=255, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sequences_created", editable=False
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sequences_updated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "sequence_number", "sequence_type", "site_id", "created_by_id"
            ).first()
            if previous and (
                previous["sequence_number"] != self.sequence_number
                or previous["sequence_type"] != self.sequence_type
                or previous["site_id"] != self.site_id
                or previous["created_by_id"] != self.created_by_id
            ):
                raise ValidationError("Sequence Number, Type, Site, dan Approved By tidak dapat diubah setelah diterbitkan.")
        super().save(*args, **kwargs)

    class Meta:
        db_table = "sequence_records"
        ordering = ["-operational_date", "-id"]
        indexes = [
            models.Index(fields=["sequence_type", "site", "operational_date"], name="sequence_re_seq_typ_f03147_idx"),
            models.Index(fields=["status"], name="sequence_re_status_74a9c1_idx"),
            models.Index(fields=["document_status"], name="sequence_re_documen_442f76_idx"),
            models.Index(fields=["ticket_number"], name="sequence_re_ticket__b8e9cf_idx"),
        ]

    def __str__(self):
        return self.sequence_number


class SequenceAuditLog(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_VOID = "void"
    ACTION_CHOICES = [(ACTION_CREATE, "Create"), (ACTION_UPDATE, "Update"), (ACTION_VOID, "Void")]

    sequence = models.ForeignKey(SequenceRecord, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_changed = models.CharField(max_length=80, blank=True, default="")
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sequence_audit_logs"
        ordering = ["-changed_at", "-id"]
        indexes = [models.Index(fields=["sequence", "changed_at"], name="sequence_au_sequenc_575dd4_idx")]

# ==========================
# v1.9.7 Checklist / Compliance
# ==========================
class ChecklistDefinition(models.Model):
    SITE_CHOICES = [("JKT2", "JKT2"), ("JKT3", "JKT3")]
    site = models.CharField(max_length=10, choices=SITE_CHOICES)
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=80, blank=True, default="")
    schedule_config = models.JSONField(default=dict, blank=True)
    items = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checklist_definitions"
        ordering = ["site", "name"]


class ChecklistSubmission(models.Model):
    STATUS_DRAFT = "Draft"
    STATUS_COMPLETED = "Completed"
    STATUS_INCOMPLETE = "Incomplete"
    STATUS_CHOICES = [(STATUS_DRAFT, STATUS_DRAFT), (STATUS_COMPLETED, STATUS_COMPLETED), (STATUS_INCOMPLETE, STATUS_INCOMPLETE)]

    definition = models.ForeignKey(ChecklistDefinition, on_delete=models.CASCADE, related_name="submissions")
    operational_date = models.DateField(default=timezone.localdate)
    shift = models.CharField(max_length=20)
    pic = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="checklist_submissions")
    site = models.CharField(max_length=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    answers = models.JSONField(default=dict, blank=True)
    is_backdated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "checklist_submissions"
        ordering = ["-operational_date", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["definition", "operational_date", "shift"], name="uniq_checklist_definition_date_shift")]


class ChecklistEvidence(models.Model):
    submission = models.ForeignKey(ChecklistSubmission, on_delete=models.CASCADE, related_name="evidence_files")
    schedule_time = models.CharField(max_length=10, blank=True, default="")
    file = models.FileField(upload_to="checklist_evidence/%Y/%m/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "checklist_evidence"


# ==========================
# v1.9.7 Remote Hands Report
# ==========================
class RemoteHandsReport(models.Model):
    SITE_CHOICES = [("JKT2", "JKT2"), ("JKT3", "JKT3")]
    TYPE_REMOTE = "Remote Hands Report"
    TYPE_CUSTOM = "Custom Remote Hands Report"
    TYPE_CHOICES = [(TYPE_REMOTE, TYPE_REMOTE), (TYPE_CUSTOM, TYPE_CUSTOM)]
    STATUS_DRAFT = "Draft"
    STATUS_COMPLETED = "Completed"
    STATUS_CHOICES = [(STATUS_DRAFT, STATUS_DRAFT), (STATUS_COMPLETED, STATUS_COMPLETED)]

    report_type = models.CharField(max_length=80, choices=TYPE_CHOICES, default=TYPE_REMOTE)
    ticket_number = models.CharField(max_length=120)
    site = models.CharField(max_length=10, choices=SITE_CHOICES)
    start_datetime = models.DateTimeField()
    finish_datetime = models.DateTimeField()
    additional_datetime = models.DateTimeField(null=True, blank=True)
    engineer = models.CharField(max_length=255)
    request_by = models.CharField(max_length=255, blank=True, default="")
    shift_leader = models.CharField(max_length=255, blank=True, default="")
    customer = models.ForeignKey(Customers, on_delete=models.PROTECT, related_name="remote_hands_reports")
    rack_number = models.CharField(max_length=255, blank=True, default="")
    task_detail = models.TextField()
    result_information = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remote_hands_reports_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "remote_hands_reports"
        ordering = ["-start_datetime", "-id"]


class RemoteHandsAttachment(models.Model):
    report = models.ForeignKey(RemoteHandsReport, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="remote_hands/%Y/%m/")
    caption = models.TextField(blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "remote_hands_attachments"

