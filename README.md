# Techmiary Institute of Technology — Institutional ERP

A production-grade, full-stack School ERP built with **Django 5.2** for **Techmiary Institute of Technology (TIT)**.

Built and maintained by **Techmiary**.

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env        # edit with your credentials
python manage.py migrate
python manage.py seed_comm_templates
python manage.py createsuperuser
gunicorn lms_project.wsgi:application --bind 0.0.0.0:8000
```

## Tech Stack

| Layer       | Technology                                     |
|-------------|------------------------------------------------|
| Backend     | Django 5.2 (Python 3.12)                      |
| Database    | PostgreSQL                                     |
| Web Server  | Gunicorn + Nginx                               |
| Email       | Gmail SMTP (App Password)                      |
| SMS         | Termii / Africa's Talking fallback             |
| Payments    | Paystack                                       |
| Frontend    | Bootstrap + custom CSS                         |
| PDF         | ReportLab                                      |
| Excel       | openpyxl                                       |

## Modules

- **Users** — Staff, Student, Parent accounts with role-based permissions
- **Academics** — Sessions, terms, classes, timetable, student promotion
- **CBT** — Computer-based testing and online exams
- **Results** — Score entry, term results, batch publishing
- **Finance** — Family wallet, fee structures, Paystack, PDF receipts, payroll
- **Hostel** — Buildings, beds, boarder profiles, exeats, visitor log, incidents
- **Communications** — Email & SMS campaigns, fee reminders, auto-notifications
- **Inventory** — Asset tracking, stock movements, maintenance, email whitelist
- **Announcements** — School-wide and class-specific with audience targeting

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
SECRET_KEY, DEBUG, ALLOWED_HOSTS
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
MASTER_STUDENT_PASSWORD, MASTER_PARENT_PASSWORD
EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
TERMII_API_KEY, TERMII_SENDER_ID
AT_API_KEY, AT_USERNAME
PAYSTACK_SECRET_KEY, PAYSTACK_PUBLIC_KEY
SCHOOL_PHONE, SCHOOL_PORTAL_URL
```

## Access Roles

| Role       | Access                                            |
|-----------|---------------------------------------------------|
| Superuser | Everything                                        |
| Admin     | All modules except Django admin                   |
| Teacher   | Classes, timetable, results, CBT                  |
| Account   | Finance, payroll, communications                  |
| Parent    | Own children's wallet, results, announcements     |
| Student   | CBT exams, results, announcements                 |

## Cron (Scheduled Campaigns)

```bash
* * * * * cd /path/to/project && python manage.py send_scheduled_campaigns >> /var/log/tit_campaigns.log 2>&1
```

## Credits

Built by **Techmiary** for **Techmiary Institute of Technology**, Nigeria.
