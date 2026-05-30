# liveclass/urls.py
from django.urls import path
from . import views

app_name = 'liveclass'

urlpatterns = [
    # Teacher
    path('teacher/course/<int:course_id>/live-classes/', views.teacher_live_classes, name='teacher_live_classes'),
    path('teacher/course/<int:course_id>/live-classes/create/', views.create_live_class, name='create_live_class'),
    path('room/<uuid:room_id>/start/', views.start_live_class, name='start_live_class'),
    path('room/<uuid:room_id>/end/', views.end_live_class, name='end_live_class'),
    path('room/<uuid:room_id>/delete/', views.delete_live_class, name='delete_live_class'),
    path('room/<uuid:room_id>/attendance/', views.live_class_attendance, name='attendance'),

    # Shared (teacher + student enter)
    path('room/<uuid:room_id>/', views.enter_live_class, name='enter_live_class'),

    # Student
    path('student/live-classes/', views.student_live_classes, name='student_live_classes'),
]
