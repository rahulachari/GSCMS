"""
Django settings for gscms project.
Goldsmith / Jewellery Workshop Management System (GSCMS)
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

IS_VERCEL = 'VERCEL' in os.environ or os.environ.get('VERCEL') == '1'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-gscms-workshop-elite-master-key-2026')

DEBUG = True

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'https://*.vercel.app',
    'https://*.now.sh',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # GSCMS app
    'workshop.apps.WorkshopConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

try:
    import whitenoise
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

MIDDLEWARE.extend([
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'workshop.middleware.AutoLoginMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
])

ROOT_URLCONF = 'gscms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            ROOT_DIR / 'frontend' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'workshop.context_processors.workshop_globals',
            ],
        },
    },
]

WSGI_APPLICATION = 'gscms.wsgi.application'

# Database
# Production-ready SQLite by default; on Vercel runs against /tmp/db.sqlite3
tmp_db = Path('/tmp/db.sqlite3')
if IS_VERCEL and tmp_db.exists():
    db_target = tmp_db
elif IS_VERCEL:
    src_db = BASE_DIR / 'db.sqlite3'
    if src_db.exists():
        try:
            import shutil
            shutil.copy2(src_db, tmp_db)
            db_target = tmp_db
        except Exception:
            db_target = src_db
    else:
        db_target = tmp_db
else:
    db_target = BASE_DIR / 'db.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': db_target,
    }
}

# Cookie-based sessions so database writes are never required for sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 4,
        }
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = False

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    ROOT_DIR / 'frontend' / 'static',
]
if IS_VERCEL:
    STATIC_ROOT = Path('/tmp/staticfiles')
else:
    STATIC_ROOT = BASE_DIR / 'staticfiles'

WHITENOISE_USE_FINDERS = True

# Media storage
MEDIA_URL = '/media/'
if IS_VERCEL:
    MEDIA_ROOT = Path('/tmp/media')
else:
    MEDIA_ROOT = BASE_DIR / 'media'

# Backups folder
if IS_VERCEL:
    BACKUPS_DIR = Path('/tmp/backups')
else:
    BACKUPS_DIR = ROOT_DIR / 'backups'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

