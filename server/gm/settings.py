"""Django settings for the GM site (memorial pages + admin).

Everything that differs between a laptop and the EC2 server comes from environment
variables, read from server/.env in development or /srv/gm/env in production.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # server/
SITE_DIR = BASE_DIR.parent  # repository root: the static website
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
	return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
	if not DEBUG:
		raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
	SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]

# Google accounts allowed into the admin (lower-case)
ADMIN_EMAILS = [e.lower() for e in env_list("ADMIN_EMAILS")]
# Who gets "new comment to approve" emails (defaults to the admins)
MODERATION_EMAILS = env_list("MODERATION_EMAILS") or ADMIN_EMAILS
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8002").rstrip("/")

DATA_DIR = Path(os.environ.get("DJANGO_DATA_DIR", BASE_DIR / "data"))

INSTALLED_APPS = [
	"django.contrib.admin",
	"django.contrib.auth",
	"django.contrib.contenttypes",
	"django.contrib.sessions",
	"django.contrib.messages",
	"django.contrib.staticfiles",
	"allauth",
	"allauth.account",
	"allauth.socialaccount",
	"allauth.socialaccount.providers.google",
	"memorials",
	"news",
]

MIDDLEWARE = [
	"django.middleware.security.SecurityMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"django.middleware.clickjacking.XFrameOptionsMiddleware",
	"allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "gm.urls"
WSGI_APPLICATION = "gm.wsgi.application"

TEMPLATES = [
	{
		"BACKEND": "django.template.backends.django.DjangoTemplates",
		"DIRS": [BASE_DIR / "templates"],
		"APP_DIRS": True,
		"OPTIONS": {
			"context_processors": [
				"django.template.context_processors.request",
				"django.contrib.auth.context_processors.auth",
				"django.contrib.messages.context_processors.messages",
			],
		},
	},
]

DATABASES = {
	"default": {
		"ENGINE": "django.db.backends.sqlite3",
		"NAME": DATA_DIR / "db.sqlite3",
		"OPTIONS": {"init_command": "PRAGMA journal_mode=WAL;"},
	}
}

# Shared between gunicorn workers (used for comment rate limiting)
CACHES = {
	"default": {
		"BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
		"LOCATION": DATA_DIR / "cache",
	}
}

AUTH_PASSWORD_VALIDATORS = [
	{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
	{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
	{"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --- Authentication: Google only, restricted to ADMIN_EMAILS ---
AUTHENTICATION_BACKENDS = [
	"django.contrib.auth.backends.ModelBackend",  # emergency superuser created with manage.py
	"allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_ADAPTER = "memorials.adapters.NoSignupAccountAdapter"
SOCIALACCOUNT_ADAPTER = "memorials.adapters.AdminOnlySocialAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
	"google": {
		"APPS": [
			{
				"client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
				"secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
				"key": "",
			}
		],
		"SCOPE": ["profile", "email"],
		"AUTH_PARAMS": {"prompt": "select_account"},
	}
}
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# --- Email (Amazon SES over SMTP in production, console in development) ---
if os.environ.get("EMAIL_HOST"):
	EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
	EMAIL_HOST = os.environ["EMAIL_HOST"]  # e.g. email-smtp.eu-west-3.amazonaws.com
	EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
	EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
	EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
	EMAIL_USE_TLS = True
	EMAIL_TIMEOUT = 15
else:
	EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get(
	"DEFAULT_FROM_EMAIL", "Pompes Funèbres et Marbrerie GM <noreply@gmfuneraire.fr>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# Admin CSS/JS (the website's own css/ and img/ are served by nginx from the site root)
STATIC_URL = "/django-static/"
STATIC_ROOT = DATA_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # form fields; uploaded files are limited in forms.py

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Private messages to families are deleted this many days after being sent
PRIVATE_COMMENT_RETENTION_DAYS = int(os.environ.get("PRIVATE_COMMENT_RETENTION_DAYS", "30"))
# Public messages refused by an admin are deleted this many days after they were received
REJECTED_COMMENT_RETENTION_DAYS = int(os.environ.get("REJECTED_COMMENT_RETENTION_DAYS", "30"))

if not DEBUG:
	SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_SECURE = True
	SECURE_HSTS_SECONDS = 3600

# --- Actualités: daily import of the agency's Facebook / Instagram posts (see README) ---
META_PAGE_ID = os.environ.get("META_PAGE_ID", "")
META_PAGE_TOKEN = os.environ.get("META_PAGE_TOKEN", "")
META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
META_IMPORT_INSTAGRAM = os.environ.get("META_IMPORT_INSTAGRAM", "1") == "1"
META_INSTAGRAM_ID = os.environ.get("META_INSTAGRAM_ID", "")  # found automatically from the Page if empty
# A post containing this tag is not copied to the site (and is hidden if it already was)
SOCIAL_OPT_OUT_TAG = os.environ.get("SOCIAL_OPT_OUT_TAG", "#pasdesite")

LOGGING = {
	"version": 1,
	"disable_existing_loggers": False,
	"handlers": {"console": {"class": "logging.StreamHandler"}},
	"loggers": {
		"memorials": {"handlers": ["console"], "level": "INFO"},
		"news": {"handlers": ["console"], "level": "INFO"},
	},
}
