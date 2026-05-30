"""
lms_project/settings.py — Techmiary SaaS ERP (multi-tenant)
"""
from pathlib import Path
from decouple import Config, Csv, RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent
config = Config(RepositoryEnv(BASE_DIR / ".env"))

SECRET_KEY = config('SECRET_KEY')
DEBUG       = config('DEBUG', default=False, cast=bool)
#ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())
ALLOWED_HOSTS = []

# Root domain — used by TenantMiddleware and portal URL generation
ROOT_DOMAIN = config('ROOT_DOMAIN', default='titmiary.edu.ng')
# Port used in local development (e.g. 8000). Leave blank in production.
DEV_PORT    = config('DEV_PORT', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    # SaaS platform
    'tenants.apps.TenantsConfig',
    'public_site.apps.PublicSiteConfig',
    # School apps (tenant-scoped)
    'users',
    'academics.apps.AcademicsConfig',
    'cbt',
    'dashboard',
    'results',
    'classroom',
    'inventory',
    'announcement',
    'timetable',
    'finance',
    'payroll',
    'hostel',
    'communications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tenants.middleware.TenantMiddleware',
    'lms_project.middleware.OneSessionPerBrowserMiddleware',
]

ROOT_URLCONF = 'lms_project.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'academics.context_processors.active_academic_context',
        'tenants.context_processors.tenant_context',
    ]},
}]

WSGI_APPLICATION = 'lms_project.wsgi.application'

"""DATABASES = {'default': {
    'ENGINE':   'django.db.backends.postgresql',
    'NAME':     config('DB_NAME'),
    'USER':     config('DB_USER'),
    'PASSWORD': config('DB_PASSWORD'),
    'HOST':     config('DB_HOST', default='localhost'),
    'PORT':     config('DB_PORT', default='5432'),
}}"""

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    # Production: switch to Redis
    # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    # 'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
}}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_DOMAIN = config('SESSION_COOKIE_DOMAIN', default=None)
CSRF_COOKIE_DOMAIN    = config('SESSION_COOKIE_DOMAIN', default=None)

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = not DEBUG

# Trust both the production domain and localhost for local dev
_is_localhost = ROOT_DOMAIN in ('localhost', '127.0.0.1')
if _is_localhost:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://*.localhost:8000',
        'http://localhost',
        'http://*.localhost',
    ]
else:
    CSRF_TRUSTED_ORIGINS = [
        f'https://{ROOT_DOMAIN}',
        f'https://*.{ROOT_DOMAIN}',
        f'https://www.{ROOT_DOMAIN}',
    ]

AUTH_USER_MODEL = 'users.User'
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/dashboard/'
AUTHENTICATION_BACKENDS = [
    'users.backends.ParentBackend',
    'django.contrib.auth.backends.ModelBackend',
]
MASTER_STUDENT_PASSWORD = config('MASTER_STUDENT_PASSWORD')
MASTER_PARENT_PASSWORD  = config('MASTER_PARENT_PASSWORD')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'
MAX_UPLOAD_SIZE = 5242880
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL  = f"Techmiary ERP <{config('EMAIL_HOST_USER')}>"

PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY')

TERMII_API_KEY   = config('TERMII_API_KEY')
TERMII_SENDER_ID = config('TERMII_SENDER_ID', default='TITMIARY')
AT_API_KEY       = config('AT_API_KEY',  default='')
AT_USERNAME      = config('AT_USERNAME', default='sandbox')
AT_SENDER_ID     = config('AT_SENDER_ID', default=None)

SCHOOL_PHONE      = config('SCHOOL_PHONE', default='')
SCHOOL_PORTAL_URL = config('SCHOOL_PORTAL_URL', default=f'https://{ROOT_DOMAIN}')
