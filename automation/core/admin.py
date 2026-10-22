from django.contrib import admin
from .models import (
    User,
    Customers,
    FloorLevel,
    Rack,
    MailingList,
    ARGroup,
    AR,
    EmailLogs,
    SiteLocation,
    SupportGroup,
    ActivityLog,
    Changelog,
    MailingGroup,
    CustomerAdditionalMailingList
)

# ========= Helper kecil untuk menampilkan M2M secara ringkas =========
def short_list(qs, limit=3):
    names = [str(x) for x in qs[:limit]]
    try:
        total = qs.count()
    except Exception:
        total = len(names)
    extra = max(total - len(names), 0)
    return ", ".join(names) + (f" (+{extra} lagi)" if extra > 0 else "")


# ==========================
# User
# ==========================
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'role', 'is_active', 'is_staff', 'created_at', 'updated_at')
    search_fields = ('username', 'role')
    list_filter = ('is_active', 'is_staff', 'role')
    ordering = ('-id',)


# ==========================
# Site Location
# ==========================
@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address')
    search_fields = ('name',)
    ordering = ('name',)


# ==========================
# Floor Level
# ==========================
@admin.register(FloorLevel)
class FloorLevelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'site_location', 'rack_location', 'desc')
    search_fields = ('name', 'rack_location', 'desc', 'site_location__name')
    list_filter = ('site_location',)
    ordering = ('-id',)
    autocomplete_fields = ('site_location',)


# ==========================
# Rack
# ==========================
@admin.register(Rack)
class RackAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_racks', 'floor_level')
    search_fields = ('name_racks', 'floor_level__name')
    list_filter = ('floor_level',)
    ordering = ('-id',)
    autocomplete_fields = ('floor_level',)


# ==========================
# Customers
# ==========================
@admin.register(Customers)
class CustomersAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name_customer',
        'authorized',
        'office_phone',
        'get_racks',
        'created_by',
        'created_at',
    )
    search_fields = ('name_customer', 'authorized', 'office_phone')
    ordering = ('-id',)
    autocomplete_fields = ('created_by',)
    filter_horizontal = ('racks',)

    @admin.display(description="Racks")
    def get_racks(self, obj: Customers):
        return short_list(obj.racks.all())


# ==========================
# AR Group
# ==========================
@admin.register(ARGroup)
class ARGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'rack', 'validity_AR', 'due_date', 'created_at')
    search_fields = ('customer__name_customer', 'validity_AR')
    list_filter = ('validity_AR', 'rack__floor_level__site_location', 'rack__floor_level')
    ordering = ('-id',)
    autocomplete_fields = ('customer', 'rack')


# ==========================
# Dynamic Mailing Group
# ==========================
@admin.register(MailingGroup)
class MailingGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "site", "is_active", "created_at", "updated_at")
    search_fields = ("name", "description", "site__name")
    list_filter = ("site", "is_active")
    filter_horizontal = ("floors",)


# ==========================
# Mailing List
# ==========================
@admin.register(MailingList)
class MailingListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('-id',)


@admin.register(CustomerAdditionalMailingList)
class CustomerAdditionalMailingListAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "email_address", "label", "created_at")
    search_fields = ("customer__name_customer", "email_address", "label")
    list_filter = ("customer",)
    autocomplete_fields = ("customer",)
    ordering = ("customer__name_customer", "email_address")


# ==========================
# AR (Authorized Person)
# ==========================
@admin.register(AR)
class ARAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'email_address',
        'authorized_name',
        'customer',
        'ar_group',
        'get_mailing_lists',
        'mobile_phone',
        'created_at',
    )
    search_fields = (
        'email_address',
        'authorized_name',
        'mobile_phone',
        'customer__name_customer',
    )
    list_filter = ('customer', 'ar_group', 'mailing_lists')
    ordering = ('-id',)
    autocomplete_fields = ('customer', 'ar_group')
    filter_horizontal = ('mailing_lists',)

    @admin.display(description="Mailing Lists")
    def get_mailing_lists(self, obj: AR):
        return short_list(obj.mailing_lists.all())


# ==========================
# Email Logs
# ==========================
@admin.register(EmailLogs)
class EmailLogsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'subject',
        'status',
        'sent_at',
        'email_account',
        'mailing_list',
        'customer',
        'user',
    )
    search_fields = (
        'subject',
        'body',
        'status',
        'email_account__email_address',
        'customer__name_customer',
        'user__username',
    )
    list_filter = ('status', 'sent_at', 'customer', 'mailing_list')
    ordering = ('-sent_at', '-id')
    autocomplete_fields = ('email_account', 'mailing_list', 'customer', 'user')


# ==========================
# Support Group
# ==========================
@admin.register(SupportGroup)
class SupportGroupAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'customer', 'rack', 'identity_number', 'access_level',
        'validity_date', 'status', 'created_at'
    )
    search_fields = ('name', 'identity_number', 'access_level', 'email_phone', 'reference_info', 'customer__name_customer')
    list_filter = ('status', 'validity_date', 'rack__floor_level__site_location', 'rack__floor_level')
    ordering = ('customer__name_customer', 'name')
    autocomplete_fields = ('customer', 'rack')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'entity_type', 'entity_label', 'status')
    search_fields = ('user__username', 'entity_type', 'entity_label', 'description')
    list_filter = ('action', 'entity_type', 'status', 'created_at')
    readonly_fields = ('user', 'action', 'entity_type', 'entity_id', 'entity_label', 'description', 'status', 'metadata', 'created_at')
    ordering = ('-created_at', '-id')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Changelog)
class ChangelogAdmin(admin.ModelAdmin):
    list_display = ('version', 'title', 'released_at', 'is_published')
    list_filter = ('is_published', 'released_at')
    search_fields = ('version', 'title')
    ordering = ('-released_at', '-id')
