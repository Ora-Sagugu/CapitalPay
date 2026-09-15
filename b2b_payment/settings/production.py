"""Production settings — Gunicorn + Nginx behind reverse proxy."""
import os
from .base import *  # noqa: F403, F401

DEBUG = False

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
]

# Honor X-Forwarded-* from Nginx
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Production traffic is HTTPS-only behind Nginx.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# Cashier / customer portal links embedded in backend responses
CASHIER_BASE_URL = os.environ.get(
    "CASHIER_BASE_URL",
    "/customer/pay",
)

# Require real secrets from environment in production
_secret = os.environ.get("DJANGO_SECRET_KEY", "")
if not _secret or "CHANGE-ME" in _secret or "insecure" in _secret.lower():
    raise RuntimeError("Set a strong DJANGO_SECRET_KEY in the production environment")
SECRET_KEY = _secret

_fernet = os.environ.get("FIELD_ENCRYPTION_KEY", "")
if not _fernet or _fernet == "ZmDc7qJ3XkL9pW2vN5sH8aB1eR4uY6tG=":
    raise RuntimeError("Set FIELD_ENCRYPTION_KEY via Fernet.generate_key() for production")
FIELD_ENCRYPTION_KEY = _fernet


# Never fall back to SQLite in production: remittance idempotency and daily
# limits rely on MySQL 8.0 InnoDB row locks and unique constraints.
from b2b_payment.db import install_pymysql, mysql_databases_config

install_pymysql()
DATABASES = {"default": mysql_databases_config(required=True)}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
}
