"""Django base settings for CapitalPay."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-CHANGE-ME-IN-PRODUCTION-xxxxxxxxxxxxxx",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# ── Application definition ──────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.merchant",
    "apps.payment",
    "apps.account",
    "apps.reconciliation",
    "apps.settlement",
    "apps.openapi",
    "apps.report",
    "apps.rbac",
    "apps.user_portal",
    "apps.agent",
    "apps.compliance",
    "apps.routing",
    "apps.param",
    "apps.adjustment",
    "apps.exchange",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "b2b_payment.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "b2b_payment.wsgi.application"

# ── Database ────────────────────────────────────────────────
# Default: SQLite. Set MYSQL_HOST to use MySQL 8.0 (same shape as production).

from b2b_payment.db import install_pymysql, mysql_databases_config  # noqa: E402

install_pymysql()

_mysql = mysql_databases_config(required=False)
if _mysql:
    DATABASES = {"default": _mysql}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_DATABASE", BASE_DIR / "db.sqlite3"),
        }
    }

# ── Cache (OpenAPI nonce anti-replay) ───────────────────────

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ── Password validation ─────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalization ────────────────────────────────────

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ── Static files ────────────────────────────────────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Official OFAC SDN.CSV / UN consolidated.xml uploads are typically several MB.
SANCTION_IMPORT_MAX_BYTES = 32 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = SANCTION_IMPORT_MAX_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = SANCTION_IMPORT_MAX_BYTES

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.rbac.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ── drf-spectacular (OpenAPI 文档) ──────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "CapitalPay API",
    "DESCRIPTION": "CapitalPay 后端接口文档 — 预下单、支付确认、退款、对账、清算、内部经营分析。指标口径见 docs/metrics.md。",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1/",
}

# ── CORS ────────────────────────────────────────────────────

CORS_ALLOW_ALL_ORIGINS = DEBUG

# ── Encryption ──────────────────────────────────────────────

FIELD_ENCRYPTION_KEY = os.environ.get(
    "FIELD_ENCRYPTION_KEY",
    "ZmDc7qJ3XkL9pW2vN5sH8aB1eR4uY6tG=",  # CHANGE IN PRODUCTION!
)

# ── Business ────────────────────────────────────────────────

ORDER_EXPIRE_MINUTES = int(os.environ.get("ORDER_EXPIRE_MINUTES", "30"))
CASHIER_BASE_URL = os.environ.get("CASHIER_BASE_URL", "http://localhost:1027/pay")
MAX_REFUND_RATIO = 1.0  # 退款金额不能超过原订单金额
RECONCILIATION_RETENTION_DAYS = 180
REPORT_MAX_RANGE_DAYS = int(os.environ.get("REPORT_MAX_RANGE_DAYS", "180"))
REPORT_MAX_PAGE_SIZE = int(os.environ.get("REPORT_MAX_PAGE_SIZE", "100"))
REPORT_MAX_EXPORT_ROWS = int(os.environ.get("REPORT_MAX_EXPORT_ROWS", "2000"))

# ── Bank / FX integration ───────────────────────────────────
BANK_GATEWAY_MODE = os.environ.get("BANK_GATEWAY_MODE", "MOCK").upper()  # MOCK | REAL
BANK_CODES = [c.strip() for c in os.environ.get("BANK_CODES", "MOCK").split(",") if c.strip()]
BANK_RECON_FETCH_MODE = os.environ.get("BANK_RECON_FETCH_MODE", "MOCK").upper()  # MOCK | SFTP | API
BANK_FX_PROVIDER_MODE = os.environ.get("BANK_FX_PROVIDER_MODE", "MOCK").upper()  # MOCK | REAL
BANK_SFTP_HOST = os.environ.get("BANK_SFTP_HOST", "")
BANK_SFTP_USER = os.environ.get("BANK_SFTP_USER", "")
BANK_SFTP_PASSWORD = os.environ.get("BANK_SFTP_PASSWORD", "")
FX_API_KEY = os.environ.get("FX_API_KEY", "")
FX_API_URL = os.environ.get("FX_API_URL", "")
# JSON-ish map via env is awkward; keep empty dict, fill per deployment
BANK_API_KEYS = {}
_raw_keys = os.environ.get("BANK_API_KEYS", "")
if _raw_keys:
    for pair in _raw_keys.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            BANK_API_KEYS[k.strip()] = v.strip()

# ── SMS ─────────────────────────────────────────────────────
SMS_PROVIDER_MODE = os.environ.get("SMS_PROVIDER_MODE", "MOCK").upper()  # MOCK | LOG | REAL
SMS_API_URL = os.environ.get("SMS_API_URL", "")
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")

# Banking / Agents modules. Set False to hide menus and skip fee splits.
ENABLE_AGENTS = True
ENABLE_BANKING = True
