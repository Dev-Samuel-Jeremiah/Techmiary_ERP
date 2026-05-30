from django.urls import path
from communications import views

app_name = 'communications'

urlpatterns = [
    path('',                              views.dashboard,            name='dashboard'),
    path('campaigns/',                    views.campaign_list,        name='campaign_list'),
    path('campaigns/new/',                views.campaign_create,      name='campaign_create'),
    path('campaigns/<int:campaign_id>/',  views.campaign_detail,      name='campaign_detail'),
    path('campaigns/<int:campaign_id>/send/', views.campaign_send,   name='campaign_send'),
    path('quick/',                        views.quick_message,        name='quick_message'),
    path('fee-reminders/',                views.fee_reminders,        name='fee_reminders'),
    path('templates/',                    views.template_list,        name='template_list'),
    path('templates/new/',                views.template_create_edit, name='template_create'),
    path('templates/<int:tpl_id>/edit/',  views.template_create_edit, name='template_edit'),
    path('templates/<int:tpl_id>/delete/', views.template_delete,    name='template_delete'),
    path('templates/<int:tpl_id>/api/',   views.get_template_content, name='template_api'),
    path('logs/',                         views.message_logs,         name='message_logs'),
    path('contact-audit/',                views.contact_audit,        name='contact_audit'),
    path('opt-outs/',                     views.opt_outs,             name='opt_outs'),
    path("hostel-reminders/",      views.hostel_reminders,      name="hostel_reminders"),
    path("result-notifications/",  views.result_notifications,  name="result_notifications"),
    path("templates/seed/",        views.seed_templates,        name="seed_templates"),
    path("test-email/",              views.test_email,            name="test_email"),
    path("login-notifications/",     views.login_notifications,   name="login_notifications"),
    path("logs/<int:log_id>/delete/", views.delete_message_log,   name="delete_log"),
    path("logs/bulk-delete/",         views.delete_logs_bulk,      name="delete_logs_bulk"),
]
