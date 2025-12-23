from django.contrib import admin
from .models import (
    User, Role, Permission, WorkflowStage, WorkflowRule, AuditLog,
    Tenant, TenantSettings, PendingChange
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin interface for Tenant model"""
    list_display = ['name', 'slug', 'is_active', 'is_trial', 'created_at']
    list_filter = ['is_active', 'is_trial', 'created_at']
    search_fields = ['name', 'slug']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug')
        }),
        ('Status', {
            'fields': ('is_active', 'is_trial', 'trial_ends_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    """Admin interface for TenantSettings model"""
    list_display = ['company_name', 'tenant', 'company_email', 'subscription_status', 'max_users', 'max_projects']
    list_filter = ['subscription_status', 'company_activity_type', 'created_at']
    search_fields = ['company_name', 'company_email', 'tenant__name', 'tenant__slug']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Company Information', {
            'fields': ('tenant', 'company_name', 'company_logo', 'company_license_number',
                      'company_email', 'company_phone', 'company_address',
                      'company_country', 'company_city', 'company_description', 'company_activity_type')
        }),
        ('Theme Settings', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('Subscription & Limits', {
            'fields': ('max_users', 'max_projects', 'subscription_status',
                      'subscription_start_date', 'subscription_end_date')
        }),
        ('Additional Settings', {
            'fields': ('currency', 'timezone', 'language')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PendingChange)
class PendingChangeAdmin(admin.ModelAdmin):
    """Admin interface for PendingChange model"""
    list_display = ['model_name', 'action', 'status', 'requested_by', 'tenant', 'created_at', 'reviewed_by']
    list_filter = ['status', 'action', 'model_name', 'created_at', 'tenant']
    search_fields = ['model_name', 'object_id', 'requested_by__email', 'reviewed_by__email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Change Information', {
            'fields': ('requested_by', 'tenant', 'action', 'model_name', 'object_id')
        }),
        ('Data', {
            'fields': ('data', 'old_data'),
            'classes': ('collapse',)
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


admin.site.register(User)
admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(WorkflowStage)
admin.site.register(WorkflowRule)
admin.site.register(AuditLog)

