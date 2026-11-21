"""Production settings. Everything secret or host-specific comes from environment variables.

Use:  DJANGO_SETTINGS_MODULE=config.settings.prod
Required: DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS. See .env.example.
"""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, MIDDLEWARE


def _env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Set the {name} environment variable.")
    return value


def _flag(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


SECRET_KEY = _env("DJANGO_SECRET_KEY", required=True)
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a random value of 50+ characters.")

DEBUG = False

ALLOWED_HOSTS = _list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS (comma-separated host names).")
CSRF_TRUSTED_ORIGINS = _list("DJANGO_CSRF_TRUSTED_ORIGINS")   # e.g. https://your-domain

# HTTPS
SECURE_SSL_REDIRECT = _flag("DJANGO_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(_env("DJANGO_HSTS_SECONDS", "3600"))   # raise once HTTPS is confirmed
SECURE_HSTS_INCLUDE_SUBDOMAINS = _flag("DJANGO_HSTS_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _flag("DJANGO_HSTS_PRELOAD", False)
if _flag("DJANGO_BEHIND_PROXY", False):   # only if your host's proxy sets X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Static files (served by WhiteNoise after `collectstatic`)
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Data locations (point these at a persistent disk on your host)
MEDIA_ROOT = _env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _env("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}