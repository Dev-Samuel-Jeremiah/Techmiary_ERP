# chat/urls.py
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('people/', views.people, name='people'),
    path('conversation/<int:conv_id>/', views.conversation, name='conversation'),
    path('start/<int:user_id>/', views.start_conversation, name='start'),
    path('api/unread/', views.unread_count, name='unread_count'),
    path('api/conversations/', views.conversations_api, name='conversations_api'),
    path('moderation/', views.moderation_log, name='moderation_log'),
]
