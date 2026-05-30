"""
tenants/admin.py
Platform superadmin view of all tenants, plans and subscriptions.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Plan, Tenant, Subscription, SubscriptionPayment, SchoolRegistration


# ── Plan ──────────────────────────────────────────────────────────────────────

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display  = ('name', 'code', 'price_per_student_term', 'price_per_student_session_display',
                     'max_students', 'is_active', 'is_public', 'sort_order')
    list_editable = ('sort_order', 'is_active', 'is_public')
    list_filter   = ('is_active', 'is_public')
    search_fields = ('name', 'code')
    readonly_fields = ('price_per_student_session_display', 'annual_savings', 'features_list_display')

    fieldsets = (
        ('Identity', {'fields': (
            'name', 'code', 'description', 'is_active', 'is_public', 'sort_order'
        )}),
        ('Per-Student Pricing', {'fields': (
            'price_per_student_term', 'terms_per_session',
            'price_per_student_session_display',
        ), 'description': 'Core pricing unit: charged per student per term. '
                          'Session = term price × number of terms.'}),
        ('Flat Rate Pricing (legacy / fallback)', {'fields': (
            'price_monthly', 'price_annual', 'annual_savings',
        ), 'classes': ('collapse',)}),
        ('Currency', {'fields': ('currency',), 'classes': ('collapse',)}),
        ('Limits (0 = unlimited)', {'fields': (
            'max_students', 'max_staff', 'max_classes'
        )}),
        ('Features', {'fields': (
            'feature_academics', 'feature_cbt', 'feature_results',
            'feature_finance', 'feature_payroll', 'feature_hostel',
            'feature_communications', 'feature_inventory', 'feature_timetable',
            'feature_announcements', 'feature_parent_portal',
            'feature_api_access', 'feature_custom_domain',
        )}),
        ('UI', {'fields': ('highlight_label', 'highlight_color')}),
    )

    def price_per_student_session_display(self, obj):
        return f"₦{obj.price_per_student_session:,.0f}"
    price_per_student_session_display.short_description = 'Price/Student/Session'

    def features_list_display(self, obj):
        from django.utils.html import format_html
        items = ''.join(
            f'<span style="display:inline-block;margin:.2rem .3rem;padding:.2rem .6rem;'
            f'border-radius:99px;font-size:.75rem;'
            f'background:{"rgba(52,211,153,.12)" if f["included"] else "rgba(255,255,255,.05)"};'
            f'color:{"#34d399" if f["included"] else "#6b7280"};">'
            f'{"✓" if f["included"] else "✗"} {f["label"]}</span>'
            for f in obj.features_list
        )
        return format_html(items)
    features_list_display.short_description = 'Features Summary'


# ── Tenant ────────────────────────────────────────────────────────────────────

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display  = ('name', 'subdomain', 'status_badge', 'plan', 'email',
                     'state', 'created_at', 'portal_link')
    list_filter   = ('status', 'plan', 'school_type', 'state', 'billing_cycle')
    search_fields = ('name', 'subdomain', 'email', 'owner_email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'activated_at', 'portal_url')
    date_hierarchy = 'created_at'

    actions = ['action_activate', 'action_suspend', 'action_start_trial']

    fieldsets = (
        ('School', {'fields': (
            'id', 'name', 'subdomain', 'custom_domain', 'logo',
            'school_type', 'state', 'country', 'address',
        )}),
        ('Contact', {'fields': ('email', 'phone', 'owner_name', 'owner_email')}),
        ('Subscription', {'fields': (
            'plan', 'billing_cycle', 'status', 'trial_ends',
            'activated_at',
        )}),
        ('Config', {'fields': ('timezone', 'currency', 'term_system')}),
        ('Paystack', {'fields': ('paystack_subaccount_code',)}),
        ('Meta', {'fields': ('created_at', 'updated_at', 'portal_url')}),
    )

    def status_badge(self, obj):
        colors = {
            'ACTIVE':    '#22c55e',
            'TRIAL':     '#3b82f6',
            'PENDING':   '#f59e0b',
            'SUSPENDED': '#ef4444',
            'CANCELLED': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:.75rem;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def portal_link(self, obj):
        return format_html('<a href="{}" target="_blank">Open Portal ↗</a>', obj.portal_url)
    portal_link.short_description = 'Portal'

    @admin.action(description='Activate selected tenants')
    def action_activate(self, request, queryset):
        for t in queryset:
            t.activate()
        self.message_user(request, f"{queryset.count()} tenant(s) activated.")

    @admin.action(description='Suspend selected tenants')
    def action_suspend(self, request, queryset):
        for t in queryset:
            t.suspend()
        self.message_user(request, f"{queryset.count()} tenant(s) suspended.")

    @admin.action(description='Start 14-day trial for selected tenants')
    def action_start_trial(self, request, queryset):
        from datetime import timedelta
        trial_end = timezone.now().date() + timedelta(days=14)
        queryset.update(status='TRIAL', trial_ends=trial_end)
        self.message_user(request, f"14-day trial started for {queryset.count()} tenant(s).")


# ── Subscription ──────────────────────────────────────────────────────────────

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ('tenant', 'plan', 'billing_cycle', 'status',
                     'amount', 'starts_at', 'ends_at', 'days_remaining')
    list_filter   = ('status', 'billing_cycle', 'plan')
    search_fields = ('tenant__name', 'tenant__subdomain', 'paystack_ref')
    raw_id_fields = ('tenant',)

    def days_remaining(self, obj):
        d = obj.days_remaining
        color = '#22c55e' if d > 14 else ('#f59e0b' if d > 3 else '#ef4444')
        return format_html('<span style="color:{};">{} days</span>', color, d)


# ── Payment ───────────────────────────────────────────────────────────────────

@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display  = ('tenant', 'plan', 'amount', 'status', 'paystack_ref', 'paid_at')
    list_filter   = ('status', 'plan')
    search_fields = ('tenant__name', 'paystack_ref')
    readonly_fields = ('id', 'paystack_data', 'created_at')


# ── School Registration ───────────────────────────────────────────────────────

@admin.register(SchoolRegistration)
class SchoolRegistrationAdmin(admin.ModelAdmin):
    list_display  = ('school_name', 'school_type', 'contact_email', 'desired_plan',
                     'status_badge', 'state', 'student_count', 'created_at', 'portal_link')
    list_filter   = ('status', 'desired_plan', 'school_type', 'state')
    search_fields = ('school_name', 'contact_email', 'subdomain')
    readonly_fields = ('created_at', 'reviewed_at', 'tenant', 'portal_link')
    actions = ['approve_registrations', 'reject_registrations']

    fieldsets = (
        ('School Info', {'fields': (
            'school_name', 'school_type', 'subdomain', 'state', 'school_address',
            'student_count', 'desired_plan', 'desired_billing', 'message',
        )}),
        ('Contact', {'fields': ('contact_name', 'contact_email', 'contact_phone')}),
        ('Review', {'fields': ('status', 'reviewed_by', 'reviewed_at', 'rejection_note', 'tenant')}),
        ('Portal Access', {'fields': ('portal_link',)}),
        ('Meta', {'fields': ('created_at',)}),
    )

    def status_badge(self, obj):
        colors = {
            'PENDING':  '#f59e0b',
            'APPROVED': '#22c55e',
            'REJECTED': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:.75rem;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def portal_link(self, obj):
        if obj.tenant:
            url = obj.tenant.portal_url
            return format_html(
                '<a href="{}" target="_blank" style="color:#3b82f6;">Open Portal ↗</a><br>'
                '<small style="color:#6b7280;">Login URL: {}</small>',
                url, url
            )
        return format_html('<span style="color:#9ca3af;">Not yet provisioned</span>')
    portal_link.short_description = 'School Portal'

    @admin.action(description='✅ Approve & activate selected school registrations')
    def approve_registrations(self, request, queryset):
        from tenants.services import approve_registration
        created = 0
        for reg in queryset.filter(status='PENDING'):
            try:
                tenant = approve_registration(reg, approved_by=request.user)
                self.message_user(
                    request,
                    f"✅ {reg.school_name} approved! Portal: {tenant.portal_url} "
                    f"— School admin can now login at that URL.",
                    level='success'
                )
                created += 1
            except Exception as e:
                self.message_user(request, f"Error for {reg.school_name}: {e}", level='error')
        if created:
            self.message_user(
                request,
                f"{created} school(s) approved. They can now login at their portal URL. "
                f"Share the portal URL with each school's administrator.",
                level='success'
            )

    @admin.action(description='❌ Reject selected school registrations')
    def reject_registrations(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='REJECTED')
        self.message_user(request, f"{updated} registration(s) rejected.")