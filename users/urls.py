from django.urls import path
from . import views
from users.views import parent_login, parent_dashboard

app_name = "users"

urlpatterns = [
    # Home page
    path('', views.home, name='home'),

    # Authentication
    path('staff/login/', views.staff_login, name='staff_login'),
    path('student/login/', views.student_login, name='student_login'),
    path('logout/', views.user_logout, name='user_logout'),

    # Staff Management
    path('staff/create/', views.create_staff, name='create_staff'),

    # Student Management
    path('students/register/', views.register_student, name='register_student'),
    path('students/generate_password/', views.generate_student_password_view, name='generate_student_password'),
    path('students/all/', views.all_students, name='all_students'),
    path('students/export/', views.export_students_excel, name='export_students_excel'),
    path('students/promote/', views.promote_students, name='promote_students'),

    # Class Management
    path('classes/manage/', views.manage_classes, name='manage_classes'),
    path('classes/delete/<int:class_id>/', views.delete_class, name='delete_class'),

    # Subject Assignment
    path('subjects/assign/', views.assign_subjects, name='assign_subjects'),

    # Advanced Subject-Teacher-Class Assignment
    path('subjects/advanced-assignment/', views.advanced_subject_assignment, name='advanced_subject_assignment'),

    # Delete assigned subject from class
    path('subjects/remove-class/<int:class_id>/<int:subject_id>/', views.remove_class_subject, name='remove_class_subject'),
    # Remove subject from student
    path('subjects/remove-student/<int:student_id>/<int:subject_id>/', views.remove_student_subject, name='remove_student_subject'),
    path('subjects/student-manager/', views.student_subject_manager, name='student_subject_manager'),
    # Attendance
    path("home/", views.attendance_home, name="attendance_home"),
    path("mark/", views.select_class_mark, name="select_class_mark"),
    path("view/", views.select_class_view, name="select_class_view"),
    path("mark/<int:class_id>/", views.mark_attendance, name="mark_attendance"),
    path("view/<int:class_id>/", views.view_attendance, name="view_attendance"),
    path('edit/<int:class_id>/<str:date>/', views.edit_attendance, name='edit_attendance'),
    path('delete/<int:class_id>/<int:student_id>/<str:date>/', views.delete_attendance, name='delete_attendance'),

    path('summary/', views.attendance_summary, name='attendance_summary'),

    path("parent/login/", parent_login, name="parent_login"),
    path("parent/dashboard/", parent_dashboard, name="parent_dashboard"),




    # Staff Management
    path('staff/permissions/', views.manage_staff_permissions, name='manage_staff_permissions'),
    path('staff/<int:staff_id>/toggle-restriction/', views.toggle_staff_restriction, name='toggle_staff_restriction'),
    path('staff/<int:staff_id>/delete/', views.delete_staff, name='delete_staff'),


    # Student Management
    path('students/edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('students/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    path('students/reset-password/<int:student_id>/', views.reset_student_password, name='reset_student_password'),


]