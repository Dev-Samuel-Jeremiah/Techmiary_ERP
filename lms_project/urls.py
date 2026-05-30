"""
lms_project/urls.py — PUBLIC SITE ONLY.

School portal requests are handled by lms_project/tenant_urls.py,
which TenantMiddleware sets as request.urlconf for any subdomain request.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('__debug__/', include('tenants.debug_urls')),
    path('admin/', admin.site.urls),
    path('', include('public_site.urls', namespace='public_site')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)