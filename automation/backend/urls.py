"""
URL configuration for automation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from core import views
from core.forms import MailGenixAuthenticationForm


urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),

    # Auth
    path('login/', auth_views.LoginView.as_view(authentication_form=MailGenixAuthenticationForm, template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # EML
    path('compose-email-eml/', views.compose_email_eml, name='compose_email_eml'),

    # Email log
    path('log-email-send/', views.log_email_send, name='log_email_send'),

    # =========================
    # API TENANTS
    # =========================
    path('api/tenants/', views.tenants_list_api, name='api_tenants_list'),
    path('api/customers/import-csv/', views.customers_csv_import, name='api_customers_import_csv'),
    path('api/customers/import-csv/template/', views.customers_csv_template, name='api_customers_csv_template'),
    path('api/tenants/<int:tenant_id>/', views.tenant_detail_api, name='api_tenant_detail'),
    
    path('api/tenants/by-customer/', views.tenants_by_customer_api, name='api_tenants_by_customer_create'),
    path('api/tenants/by-customer/<int:customer_id>/', views.tenants_by_customer_api, name='api_tenants_by_customer'),
    path('api/tenants/by-customer/<int:customer_id>/rack/<int:rack_id>/', 
         views.delete_customer_rack_api, name='api_delete_customer_rack'),

    path('tenants/add/', views.tenants_add_page, name='tenants_add'),

    # Autocomplete
    path('api/floors/autocomplete/', views.floor_autocomplete_api, name='api_floor_autocomplete'),
    path('api/racks/autocomplete/', views.rack_autocomplete_api, name='api_rack_autocomplete'),
    path('api/customers/autocomplete/', views.customer_autocomplete_api, name='api_customer_autocomplete'),
    path('api/customers/<int:customer_id>/prefill/', views.customer_prefill_api, name='api_customer_prefill'),
    path('api/customers/explorer/', views.customer_explorer_api, name='api_customer_explorer'),
    path('api/customers/<int:customer_id>/workspace/', views.customer_workspace_api, name='api_customer_workspace'),
    path('api/customers/profile/', views.customer_profile_create_api, name='api_customer_profile_create'),
    path('api/customers/<int:customer_id>/profile/', views.customer_profile_api, name='api_customer_profile'),
    path('api/customers/<int:customer_id>/support-groups/', views.customer_support_groups_api, name='api_customer_support_groups'),
    path('api/customers/<int:customer_id>/support-groups/import-csv/', views.customer_support_groups_csv_import, name='api_customer_support_groups_import_csv'),
    path('api/support-groups/import-csv/template/', views.support_groups_csv_template, name='api_support_groups_csv_template'),
    path('api/support-groups/<int:support_id>/', views.support_group_detail_api, name='api_support_group_detail'),

    # =========================
    # Mailing List Template
    # =========================
    path('render-email-template/', views.render_email_template, name='render_email_template'),
    path('api/mailing/recipients/', views.mailing_recipients_api, name='api_mailing_recipients'),
    path('api/mailing-groups/', views.mailing_groups_api, name='api_mailing_groups'),
    path('api/mailing-groups/<int:group_id>/', views.mailing_group_detail_api, name='api_mailing_group_detail'),
    path('api/live-state/', views.live_state_api, name='api_live_state'),

    # Sequence Management v1.9.6
    path('api/sequences/', views.sequences_api, name='api_sequences'),
    path('api/sequences/preview/', views.sequence_preview_api, name='api_sequence_preview'),
    path('api/sequences/customers/', views.sequence_customers_api, name='api_sequence_customers'),
    path('api/sequences/live-state/', views.sequence_live_state_api, name='api_sequence_live_state'),
    path('api/sequences/<int:sequence_id>/', views.sequence_detail_api, name='api_sequence_detail'),
    path('api/sequences/<int:sequence_id>/void/', views.sequence_void_api, name='api_sequence_void'),

    # =========================
    # User Management
    # =========================
    path('users/', views.users_page, name='users_page'),  # Page admin-only
    path('api/users/', views.users_api, name='api_users_list_create'),  # GET, POST
    path('api/users/<int:user_id>/', views.user_detail_api, name='api_user_detail'),  # PUT/PATCH, DELETE


    # v1.9.7 Customer Associations
    path('api/customers/<int:customer_id>/associations/', views.customer_associations_api, name='api_customer_associations'),
    path('api/customer-associations/<int:association_id>/', views.customer_association_detail_api, name='api_customer_association_detail'),

    # v1.9.7 Sequence admin actions/report (existing v1.9.6 schema preserved)
    path('api/sequences/<int:sequence_id>/audit/', views.sequence_audit_api, name='api_sequence_audit'),
    path('reports/sequence.xlsx', views.sequence_report_excel, name='sequence_report_excel'),

    # v1.9.7 Checklist / Compliance
    path('api/checklists/', views.checklists_api, name='api_checklists'),
    path('api/checklists/history/', views.checklist_history_api, name='api_checklist_history'),
    path('api/checklists/compliance/', views.checklist_compliance_api, name='api_checklist_compliance'),
    path('reports/checklists.xlsx', views.checklist_report_excel, name='checklist_report_excel'),

    # v1.9.7 Remote Hands
    path('api/reports/remote-hands/', views.remote_hands_api, name='api_remote_hands'),
    path('reports/remote-hands/<int:report_id>.pdf', views.remote_hands_pdf, name='remote_hands_pdf'),
    path('reports/remote-hands/<int:report_id>.docx', views.remote_hands_docx, name='remote_hands_docx'),
]
