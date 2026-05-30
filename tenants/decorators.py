"""
tenants/decorators.py
──────────────────────
Drop-in replacements for @login_required that also enforce:
  1. There IS a tenant on the request (not root domain)
  2. The tenant is accessible (not suspended / expired)
  3. Optionally: the tenant's plan includes the required feature

Usage:

    from tenants.decorators import tenant_login_required, feature_required

    @tenant_login_required
    def my_view(request): ...

    @tenant_login_required
    @feature_required('finance')
    def finance_view(request): ...
"""

from functools import wraps
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required


def tenant_login_required(view_func):
    """
    Ensures:
      - User is authenticated
      - request.tenant exists and is accessible

    If tenant is None (root domain), redirects to the public site.
    If tenant is suspended/expired, the TenantMiddleware already handles it,
    but this provides a belt-and-suspenders guard inside views.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)

        if tenant is None:
            # Called on root domain — redirect to public landing
            return redirect('/')

        if not request.user.is_authenticated:
            return redirect(f'{tenant.portal_url}/')

        if not tenant.is_accessible:
            return render(request, 'tenants/suspended.html',
                          {'tenant': tenant}, status=402)

        return view_func(request, *args, **kwargs)

    return wrapper


def feature_required(feature_code):
    """
    Decorator factory. Blocks access if the tenant's plan does not
    include the given feature.

    @tenant_login_required
    @feature_required('hostel')
    def hostel_dashboard(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if tenant is None or not tenant.has_feature(feature_code):
                return render(request, 'tenants/feature_locked.html', {
                    'feature':       feature_code,
                    'feature_label': feature_code.replace('_', ' ').title(),
                    'tenant':        tenant,
                    'upgrade_url':   '/subscription/upgrade/',
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_staff_required(view_func):
    """
    Decorator: must be a staff member with ADMIN role for this tenant,
    or a Django superuser.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect('/')
        if user.is_superuser:
            return view_func(request, *args, **kwargs)

        tenant = getattr(request, 'tenant', None)
        staff_qs = user.staff_profiles.filter(tenant=tenant)
        if not staff_qs.filter(role='ADMIN').exists():
            return render(request, 'tenants/403.html', status=403)

        return view_func(request, *args, **kwargs)
    return wrapper
