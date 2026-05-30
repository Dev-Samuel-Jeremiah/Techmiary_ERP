"""
lms_project/tenant_urls.py — SCHOOL PORTAL ONLY.

This file is loaded INSTEAD of urls.py when a subdomain is detected.
TenantMiddleware sets:  request.urlconf = 'lms_project.tenant_urls'

This means wda.localhost:8000/ will NEVER see the landing page —
it goes straight to the school's home/login page.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('__debug__/', include('tenants.debug_urls')),
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('cbt/', include('cbt.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('academics/', include('academics.urls')),
    path('results/', include('results.urls')),
    path('classroom/', include('classroom.urls')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('announcement/', include('announcement.urls')),
    path('timetable/', include('timetable.urls', namespace='timetable')),
    path('finance/', include('finance.urls', namespace='finance')),
    path('payroll/', include('payroll.urls', namespace='payroll')),
    path('hostel/', include('hostel.urls', namespace='hostel')),
    path('communications/', include('communications.urls', namespace='communications')),
    path('liveclass/', include('liveclass.urls', namespace='liveclass')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('subscription/', include('tenants.school_urls', namespace='subscription')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)