"""
tenants/middleware.py
─────────────────────
TenantMiddleware — attaches the correct Tenant object to every request.

Resolution order:
  1. Extract subdomain from HTTP_HOST.
  2. Look up Tenant by subdomain (cached in memory via simple dict).
  3. Check tenant.is_accessible; if suspended/cancelled → 402/503.
  4. Attach request.tenant; set thread-local for use in managers/signals.

For the root domain (titmiary.edu.ng) — the public site — request.tenant = None.
"""

import threading
from django.http import HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

_thread_local = threading.local()

# Do NOT read ROOT_DOMAIN at module level — settings may not be fully loaded yet.
# Always read from settings at request time (inside _resolve_tenant).
TENANT_CACHE_TIMEOUT = 60  # seconds — short so plan/status changes propagate quickly


def _get_root_domain():
    """Read ROOT_DOMAIN from settings at request time so .env is respected."""
    return getattr(settings, 'ROOT_DOMAIN', 'titmiary.edu.ng')


def get_current_tenant():
    """Return the tenant bound to the current thread (usable in signals/models)."""
    return getattr(_thread_local, 'tenant', None)


def set_current_tenant(tenant):
    _thread_local.tenant = tenant


def clear_current_tenant():
    _thread_local.tenant = None


class TenantMiddleware:
    """
    Must be placed AFTER SessionMiddleware and AuthenticationMiddleware
    in MIDDLEWARE settings so request.user is available.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._resolve_tenant(request)
        request.tenant = tenant
        set_current_tenant(tenant)

        if tenant is not None:
            # ── Block inaccessible tenants ───────────────────────────────
            if tenant.status == 'PENDING':
                # Not yet approved by platform admin — show a friendly holding page
                return render(request, 'tenants/pending_approval.html',
                              {'tenant': tenant}, status=200)
            if tenant.status == 'SUSPENDED':
                return render(request, 'tenants/suspended.html',
                              {'tenant': tenant}, status=402)
            if tenant.status == 'CANCELLED':
                return render(request, 'tenants/cancelled.html',
                              {'tenant': tenant}, status=410)
            if tenant.trial_expired:
                return render(request, 'tenants/trial_expired.html',
                              {'tenant': tenant}, status=402)

            # ── Inject tenant into session for later use ─────────────────
            request.session['tenant_id'] = str(tenant.id)

            # ── Route to school portal URL conf ──────────────────────────
            # This makes Django use tenant_urls.py instead of the default
            # urls.py (which only has public site routes). This is the key
            # to preventing the redirect loop and landing page showing up
            # on subdomain requests.
            request.urlconf = 'lms_project.tenant_urls'

        response = self.get_response(request)
        clear_current_tenant()
        return response

    def _resolve_tenant(self, request):
        host = request.get_host().split(':')[0].lower()
        root = _get_root_domain()

        # Public site — no tenant
        if host == root or host == f'www.{root}':
            return None

        # Treat bare localhost / 127.0.0.1 as public site (local dev)
        if host in ('localhost', '127.0.0.1'):
            return None

        # Subdomain-based (e.g. wda.localhost or wda.titmiary.edu.ng)
        if host.endswith(f'.{root}'):
            subdomain = host[: -(len(root) + 1)]
            return self._lookup(subdomain=subdomain)

        # Custom domain
        return self._lookup(custom_domain=host)

    @staticmethod
    def _lookup(subdomain=None, custom_domain=None):
        from tenants.models import Tenant  # avoid circular import

        if subdomain:
            cache_key = f'tenant:sub:{subdomain}'
            field, value = 'subdomain', subdomain
        else:
            cache_key = f'tenant:domain:{custom_domain}'
            field, value = 'custom_domain', custom_domain

        cached = cache.get(cache_key)
        if cached == '__NOT_FOUND__':
            return None
        if cached is not None:
            # Re-fetch to get live status (cache only stores pk)
            try:
                return Tenant.objects.select_related('plan').get(pk=cached)
            except Tenant.DoesNotExist:
                cache.delete(cache_key)

        try:
            tenant = Tenant.objects.select_related('plan').get(**{field: value})
            cache.set(cache_key, str(tenant.pk), TENANT_CACHE_TIMEOUT)
            return tenant
        except Tenant.DoesNotExist:
            cache.set(cache_key, '__NOT_FOUND__', TENANT_CACHE_TIMEOUT)
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Feature-gate decorator / mixin
# ─────────────────────────────────────────────────────────────────────────────

from functools import wraps
from django.http import HttpResponseForbidden


def feature_required(feature_code):
    """
    View decorator. Returns 403 if the tenant's plan does not include
    the requested feature, or if there is no tenant on the request.

    Usage:
        @feature_required('finance')
        def my_view(request):  ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if tenant is None or not tenant.has_feature(feature_code):
                return render(request, 'tenants/feature_locked.html',
                              {'feature': feature_code, 'tenant': tenant},
                              status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class FeatureRequiredMixin:
    """
    Class-based view mixin equivalent of @feature_required.

    class FinanceDashboard(FeatureRequiredMixin, View):
        required_feature = 'finance'
    """
    required_feature = None

    def dispatch(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if self.required_feature and (
            tenant is None or not tenant.has_feature(self.required_feature)
        ):
            return render(request, 'tenants/feature_locked.html',
                          {'feature': self.required_feature, 'tenant': tenant},
                          status=403)
        return super().dispatch(request, *args, **kwargs)