from django.urls import path
from . import views

app_name = 'timetable'

urlpatterns = [
    # Public / student / teacher views
    path('', views.timetable_index, name='index'),
    path('my-timetable/', views.teacher_timetable, name='teacher_timetable'),

    # Admin: Configurations
    path('admin/', views.admin_index, name='admin_index'),
    path('admin/config/create/', views.config_create, name='config_create'),
    path('admin/config/<int:pk>/', views.config_detail, name='config_detail'),
    path('admin/config/<int:pk>/edit/', views.config_edit, name='config_edit'),
    path('admin/config/<int:pk>/delete/', views.config_delete, name='config_delete'),
    path('admin/config/<int:config_pk>/generate/', views.generate, name='generate'),

    # Admin: Time Slots
    path('admin/slots/', views.slot_list, name='slot_list'),
    path('admin/slots/create/', views.slot_create, name='slot_create'),
    path('admin/slots/<int:pk>/edit/', views.slot_edit, name='slot_edit'),
    path('admin/slots/<int:pk>/delete/', views.slot_delete, name='slot_delete'),

    # Admin: Teacher-Subject-Class Assignments
    path('admin/config/<int:config_pk>/assignments/add/', views.assignment_create, name='assignment_create'),
    path('admin/assignments/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('admin/assignments/<int:pk>/delete/', views.assignment_delete, name='assignment_delete'),

    # Admin: Preview, Publish & Export
    path('admin/generated/<int:pk>/', views.preview, name='preview'),
    path('admin/generated/<int:pk>/publish/', views.publish, name='publish'),
    path('admin/generated/<int:pk>/delete/', views.delete_generated, name='delete_generated'),
    path('admin/generated/<int:pk>/export/', views.export_excel, name='export_excel'),

    # Admin: Day Overrides (e.g. custom Friday schedule)
    path('admin/config/<int:config_pk>/overrides/', views.day_override_list, name='day_override_list'),
    path('admin/config/<int:config_pk>/overrides/create/', views.day_override_create, name='day_override_create'),
    path('admin/config/<int:config_pk>/overrides/<int:pk>/', views.day_override_detail, name='day_override_detail'),
    path('admin/config/<int:config_pk>/overrides/<int:pk>/edit/', views.day_override_edit, name='day_override_edit'),
    path('admin/config/<int:config_pk>/overrides/<int:pk>/delete/', views.day_override_delete, name='day_override_delete'),

    # Admin: Special Slots (inside a day override)
    path('admin/overrides/<int:override_pk>/slots/add/', views.special_slot_create, name='special_slot_create'),
    path('admin/special-slots/<int:pk>/edit/', views.special_slot_edit, name='special_slot_edit'),
    path('admin/special-slots/<int:pk>/delete/', views.special_slot_delete, name='special_slot_delete'),
]
