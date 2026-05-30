# liveclass/apps.py
from django.apps import AppConfig


class LiveclassConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'liveclass'
    verbose_name = 'Live Classes'
