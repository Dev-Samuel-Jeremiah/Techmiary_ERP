"""public_site/urls.py"""
from django.urls import path
from . import views

app_name = 'public_site'

urlpatterns = [
    path('',                        views.landing,                       name='landing'),
    path('pricing/',                views.pricing,                       name='pricing'),
    path('register/',               views.register_school,               name='register'),
    path('register/done/',          views.register_done,                 name='register_done'),
    path('register/payment-callback/', views.registration_payment_callback, name='register_payment_callback'),
    path('webhook/paystack/',       views.paystack_webhook,              name='paystack_webhook'),
    path('api/check-subdomain/',    views.check_subdomain,               name='check_subdomain'),
]