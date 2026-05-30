from django.urls import path
from payroll import views

app_name = "payroll"

urlpatterns = [
    path("",                                        views.payroll_dashboard, name="dashboard"),
    path("staff/add/",                              views.add_staff_payroll, name="add_staff"),
    path("process/<int:payroll_id>/",               views.process_salary,    name="process_salary"),
    path("payslip/<int:payroll_id>/<int:month>/<int:year>/",
                                                    views.staff_payslip,     name="payslip"),
]
