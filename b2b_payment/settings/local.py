"""Local development settings — SQLite (or MYSQL_HOST) + LocMem (inherits from base)."""
from .base import *  # noqa: F403, F401

# ── Debug toolbar-friendly ──────────────────────────────────
DEBUG = True
ALLOWED_HOSTS = ["*"]

# ── Valid Fernet key for local dev ──────────────────────────
FIELD_ENCRYPTION_KEY = "qYB6TjaUwMu_0AhYdtvdTDkVaPB7R7lMxUfLBvtPFNM="

# ── CORS for frontend dev ───────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ["*"]

# ── Enable BrowsableAPIRenderer for local debugging ──────────
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# ── Media files for local dev (KYC uploads) ──────────────────
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
