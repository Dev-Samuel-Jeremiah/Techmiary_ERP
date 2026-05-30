"""
TEMPORARY DEBUG VIEW — delete after fixing.
Add to urls.py:  path('__debug__/', include('tenants.debug_urls')),
Then visit:      http://wda.localhost:8000/__debug__/
"""
from django.urls import path
from django.http import JsonResponse
from django.conf import settings


def tenant_debug(request):
    from tenants.models import Tenant

    host_raw = request.META.get('HTTP_HOST', 'NOT SET')
    host_parsed = request.get_host()
    host_no_port = host_parsed.split(':')[0].lower()
    root = getattr(settings, 'ROOT_DOMAIN', 'NOT SET')

    # Manually replicate middleware logic
    is_root = host_no_port == root or host_no_port == f'www.{root}'
    is_bare_localhost = host_no_port in ('localhost', '127.0.0.1')
    is_subdomain = host_no_port.endswith(f'.{root}')
    subdomain = host_no_port[:-(len(root) + 1)] if is_subdomain else None

    # Check DB
    tenant_in_db = None
    if subdomain:
        t = Tenant.objects.filter(subdomain=subdomain).first()
        if t:
            tenant_in_db = {
                'id': str(t.id),
                'name': t.name,
                'subdomain': t.subdomain,
                'status': t.status,
                'plan': str(t.plan),
            }

    return JsonResponse({
        '1_HTTP_HOST_raw': host_raw,
        '2_get_host()': host_parsed,
        '3_host_no_port': host_no_port,
        '4_ROOT_DOMAIN_setting': root,
        '5_is_root_domain': is_root,
        '6_is_bare_localhost': is_bare_localhost,
        '7_is_subdomain_match': is_subdomain,
        '8_extracted_subdomain': subdomain,
        '9_tenant_in_db': tenant_in_db,
        '10_request.tenant': str(getattr(request, 'tenant', 'ATTRIBUTE NOT SET')),
        '11_ALLOWED_HOSTS': settings.ALLOWED_HOSTS,
    }, json_dumps_params={'indent': 2})


urlpatterns = [
    path('', tenant_debug, name='tenant_debug'),
]