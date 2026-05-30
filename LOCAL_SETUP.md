# Techmiary SaaS ERP — Local Development Setup Guide

## Issues Fixed in This Release

| # | Issue | Fix Applied |
|---|-------|-------------|
| 1 | `school_type` migration error | Added `school_type`, `owner_name`, `owner_email`, `billing_cycle`, `desired_billing` fields to models + fresh migration |
| 2 | Site using `titmiary.edu.ng` (not hosted yet) | `.env` now uses `ROOT_DOMAIN=localhost` — works fully offline |
| 3 | No school approval workflow | Admin now has ✅ Approve / ❌ Reject actions with portal URL shown after approval |
| 4 | Landing page font / design | Improved (see landing page section) |
| 5 | How schools login | Explained below — subdomain login on localhost |
| 6 | Portal link opens `wda.titmiary.edu.ng` (not working) | Portal URLs now use `http://slug.localhost:8000` in dev mode |

---

## Step 1 — Initial Setup

```bash
cd lms_project_base

# Create and activate virtualenv
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Copy the fixed .env (already configured for local dev)
# .env is already set to ROOT_DOMAIN=localhost

# Run migrations
python manage.py migrate

# Create your superuser (platform admin)
python manage.py createsuperuser

# Seed subscription plans
python manage.py seed_plans

# Collect static files
python manage.py collectstatic --noinput
```

---

## Step 2 — Configure `/etc/hosts` for Subdomain Testing

Since you're on **localhost**, browsers don't naturally support subdomains like
`wda.localhost`. You must add each school's subdomain manually to your hosts file.

**On Linux/Mac:**
```bash
sudo nano /etc/hosts
```

**On Windows:**
Open `C:\Windows\System32\drivers\etc\hosts` as Administrator.

**Add these lines:**
```
127.0.0.1  localhost
127.0.0.1  wda.localhost
127.0.0.1  yourschool.localhost
```

Replace `wda` and `yourschool` with the actual subdomains you register.
You only need to add a school once.

---

## Step 3 — Run the Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

---

## Step 4 — How the School Approval & Login Flow Works

### A) School Registers
- Go to `http://localhost:8000/` (the landing page)
- Click **"Register Your School"**
- Fill in the form (school name, subdomain, contact info, plan)
- On submit → a `SchoolRegistration` record is created with status `PENDING`
- An email notification is sent to you (the platform admin)

### B) You Approve the School (as Platform Admin)
1. Go to `http://localhost:8000/admin/`
2. Login with your superuser account
3. Navigate to **Tenants → School Registrations**
4. Find the pending registration (shown with 🟡 Pending badge)
5. Tick the checkbox next to it
6. In the **Action** dropdown, select **"✅ Approve & activate selected school registrations"**
7. Click **Go**
8. The system will:
   - Create a `Tenant` record for the school
   - Start a 14-day free trial automatically
   - Show you the portal URL (e.g. `http://wda.localhost:8000`)
   - Send a welcome email to the school contact

### C) School Admin Logs In
After approval, the school's administrator logs in at **their subdomain URL**:
```
http://wda.localhost:8000/
```
(replace `wda` with their chosen subdomain)

The login page will be the school's own portal login — not the platform admin.

> ⚠️ **Important**: Make sure you've added `wda.localhost` to your `/etc/hosts`
> file (Step 2) before trying to access the school portal.

### D) School Admin Sets Up Their School
Once logged in at `http://wda.localhost:8000/`, the school admin can:
- Add staff accounts (via `/admin/` panel or school dashboard)
- Set up academic sessions and terms
- Add students and classes
- Configure the CBT platform
- Manage finance, timetable, etc.

---

## How Tenant Isolation Works

Every request goes through `TenantMiddleware`:
- `http://localhost:8000/` → Public site (no tenant) — landing page, registration, pricing
- `http://wda.localhost:8000/` → White Diamonds Academy portal (tenant = WDA)
- `http://school2.localhost:8000/` → Another school's portal (completely separate data)

All data in the system is filtered by `tenant`, so School A cannot see School B's data.

---

## Production Upgrade Checklist

When you're ready to go live at `titmiary.edu.ng`:

1. In `.env`, change:
   ```
   ROOT_DOMAIN=titmiary.edu.ng
   DEV_PORT=
   ALLOWED_HOSTS=titmiary.edu.ng,.titmiary.edu.ng
   SESSION_COOKIE_DOMAIN=.titmiary.edu.ng
   ```
2. Configure your web server (Nginx) with a wildcard subdomain:
   ```nginx
   server_name titmiary.edu.ng *.titmiary.edu.ng;
   ```
3. Get a wildcard SSL certificate (e.g. via Let's Encrypt with DNS challenge)
4. Set `DEBUG=False` and configure `STATIC_ROOT` + Whitenoise or Nginx static serving
5. Switch to Redis cache (uncomment in settings.py)

---

## Common Issues

### "Invalid HTTP_HOST header" error
Add the subdomain to `ALLOWED_HOSTS` in `.env`:
```
ALLOWED_HOSTS=localhost,127.0.0.1,.localhost
```
The `.localhost` with a leading dot allows ALL subdomains of localhost.

### School portal shows landing page instead of school portal
The subdomain is not in `/etc/hosts`. Add it (Step 2).

### Migration errors about `school_type`, `owner_name`, etc.
These fields were missing from the original models. The fixed migration in
`tenants/migrations/0001_initial.py` includes all fields. Run:
```bash
python manage.py migrate --run-syncdb
```

### Can't access `http://wda.localhost:8000` after approval
1. Check `/etc/hosts` — `wda.localhost` must be there
2. Check that Django is running on `0.0.0.0:8000` (not just `127.0.0.1:8000`)
3. Confirm the tenant status is TRIAL or ACTIVE in the admin panel
