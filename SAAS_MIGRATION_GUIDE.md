# Techmiary SaaS ERP — Multi-Tenant Migration Guide

## Architecture Overview

```
titmiary.edu.ng                → Public site (landing, pricing, registration)
sunshine.titmiary.edu.ng       → Sunshine Academy portal
graceland.titmiary.edu.ng      → Graceland Academy portal
brightfuture.titmiary.edu.ng   → Bright Future College portal
```

**Isolation model**: Shared database + shared Django process.
Every app model carries a `tenant` FK. The `TenantMiddleware` resolves
the subdomain on every request and sets `request.tenant`. The
`TenantManager` scopes all querysets automatically.

---

## Step-by-Step Deployment

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your real values
```

### 3. Run migrations

```bash
# Create tenants + public_site tables
python manage.py makemigrations tenants
python manage.py makemigrations

# Apply all migrations
python manage.py migrate
```

### 4. Seed default plans

```bash
python manage.py seed_plans
# Use --force to update existing plans
python manage.py seed_plans --force
```

### 5. Create platform superuser

```bash
python manage.py createsuperuser
# This user is the Techmiary platform admin — NOT a school user
```

### 6. Collect static files

```bash
python manage.py collectstatic --noinput
```

### 7. Start the server

```bash
# Development
python manage.py runserver

# Production (Gunicorn)
gunicorn lms_project.wsgi:application \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/tit/access.log \
  --error-logfile /var/log/tit/error.log
```

---

## Nginx Configuration (Subdomain Wildcard)

```nginx
# /etc/nginx/sites-available/titmiary

# Root domain + all subdomains → same Gunicorn instance
server {
    listen 443 ssl http2;
    server_name titmiary.edu.ng *.titmiary.edu.ng;

    ssl_certificate     /etc/letsencrypt/live/titmiary.edu.ng/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/titmiary.edu.ng/privkey.pem;

    # Wildcard cert required for subdomain SSL:
    # sudo certbot certonly --dns-cloudflare -d titmiary.edu.ng -d *.titmiary.edu.ng

    client_max_body_size 10M;

    location /static/ {
        alias /path/to/project/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /path/to/project/mediafiles/;
    }

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout    60s;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name titmiary.edu.ng *.titmiary.edu.ng;
    return 301 https://$host$request_uri;
}
```

---

## DNS Configuration (Cloudflare recommended)

| Type  | Name    | Value              | Proxy |
|-------|---------|--------------------|-------|
| A     | @       | YOUR_SERVER_IP     | ✓     |
| A     | www     | YOUR_SERVER_IP     | ✓     |
| A     | *       | YOUR_SERVER_IP     | ✓     |

The wildcard `*` A record routes all subdomains to your server.
Nginx passes `Host: schoolname.titmiary.edu.ng` to Django.
`TenantMiddleware` reads the subdomain and loads the correct Tenant.

---

## Adding Tenant FK to Existing App Models

Each existing app model needs:
1. Import `TenantModelMixin` from `tenants.managers`
2. Add it as a base class
3. Run `makemigrations` + `migrate`

**Example** (academics/models.py):

```python
# BEFORE
class AcademicSession(models.Model):
    name = models.CharField(max_length=50)
    ...

# AFTER
from tenants.managers import TenantModelMixin

class AcademicSession(TenantModelMixin, models.Model):
    name = models.CharField(max_length=50)
    ...
    # tenant FK + TenantManager are inherited from TenantModelMixin
```

Run the helper to see all models that need updating:
```bash
python manage.py add_tenant_fk
```

---

## Adding Feature Gates to Views

```python
from tenants.decorators import tenant_login_required, feature_required

# Basic — just requires login + valid tenant
@tenant_login_required
def my_view(request): ...

# Feature-gated — shows upgrade prompt if plan doesn't include it
@tenant_login_required
@feature_required('finance')
def finance_dashboard(request): ...

# Class-based views
from tenants.middleware import FeatureRequiredMixin

class HostelDashboard(FeatureRequiredMixin, View):
    required_feature = 'hostel'
```

---

## Feature Gates in Templates

```html
{% load tenant_tags %}

{# Show/hide based on plan #}
{% if_feature 'finance' %}
  <a href="{% url 'finance:admin_dashboard' %}">Finance</a>
{% else_feature %}
  <a href="/subscription/upgrade/" class="locked">Finance 🔒</a>
{% endif_feature %}

{# Display plan limit #}
Students: {{ tenant|plan_limit:'students' }}
```

---

## Plan Management (Django Admin)

Go to `/admin/tenants/plan/` to:
- Edit plan names, pricing, feature flags
- Enable/disable plans from the public pricing page
- Update sort order (drag to reorder on pricing page)

Go to `/admin/tenants/tenant/` to:
- View all registered schools
- Activate, suspend, or start trials
- See plan/status at a glance

Go to `/admin/tenants/schoolregistration/` to:
- Review pending school applications
- Approve (auto-creates Tenant + sends welcome email)
- Reject with a note (sends rejection email)

---

## Paystack Webhook Setup

1. Go to Paystack Dashboard → Settings → Webhooks
2. Add webhook URL: `https://titmiary.edu.ng/webhook/paystack/`
3. Paystack sends `charge.success` on every successful payment
4. `handle_paystack_webhook()` in `tenants/services.py` verifies the
   HMAC-SHA512 signature and activates the subscription automatically

---

## Scheduled Tasks

```bash
# Crontab (crontab -e)
# Check for expired trials and downgrade/notify (implement as needed)
0 8 * * * cd /path/to/project && python manage.py check_trial_expirations >> /var/log/tit/trials.log 2>&1

# Send scheduled communications campaigns
* * * * * cd /path/to/project && python manage.py send_scheduled_campaigns >> /var/log/tit/campaigns.log 2>&1
```

---

## New Files Added (SaaS layer)

```
tenants/
├── models.py           Plan, Tenant, Subscription, SubscriptionPayment, SchoolRegistration
├── managers.py         TenantQuerySet, TenantManager, TenantModelMixin
├── middleware.py       TenantMiddleware, feature_required decorator
├── decorators.py       tenant_login_required, feature_required, admin_staff_required
├── context_processors.py  tenant, tenant_plan, is_on_trial, trial_days
├── services.py         approve_registration, start_trial, activate_subscription, handle_paystack_webhook
├── admin.py            Platform admin for plans, tenants, registrations
├── school_urls.py      /subscription/* routes within each school portal
├── school_views.py     Subscription status, upgrade, Paystack checkout, callback
├── templatetags/
│   └── tenant_tags.py  {% if_feature %}, {% upgrade_prompt %}, {{ tenant|plan_limit }}
└── management/commands/
    ├── seed_plans.py       python manage.py seed_plans
    └── add_tenant_fk.py    python manage.py add_tenant_fk

public_site/
├── views.py            landing, pricing, register_school, check_subdomain, paystack_webhook
├── urls.py             / /pricing/ /register/ /register/done/ /webhook/paystack/
└── apps.py

templates/
├── public_site/
│   ├── landing.html        Full SaaS marketing landing page
│   ├── pricing.html        Pricing page (dynamic from DB)
│   ├── register.html       3-step school registration form
│   └── register_done.html  Success page with next-steps timeline
└── tenants/
    ├── feature_locked.html     403 — plan upgrade prompt
    ├── suspended.html          402 — account suspended
    ├── trial_expired.html      402 — trial over, choose plan
    └── school/
        ├── subscription_status.html   School billing dashboard
        ├── upgrade_plan.html          Plan selector with billing toggle
        ├── payment_success.html       Post-Paystack success
        └── payment_error.html         Payment failure
```
