"""
tenants/school_urls.py
─────────────────────────
URLs available within a school portal for subscription management.
Mounted at /subscription/ on every school subdomain.
"""
from django.urls import path
from . import school_views

app_name = 'subscription'

urlpatterns = [
    path('',              school_views.subscription_status, name='status'),
    path('upgrade/',      school_views.upgrade_plan,        name='upgrade'),
    path('checkout/',     school_views.initiate_payment,    name='checkout'),
    path('callback/',     school_views.payment_callback,    name='callback'),
    path('invoices/',     school_views.invoices,            name='invoices'),
    path('calculate/',    school_views.calculate_price,     name='calculate'),
]