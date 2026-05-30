# liveclass/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/liveclass/(?P<room_id>[0-9a-f-]+)/$', consumers.LiveClassConsumer.as_asgi()),
]
