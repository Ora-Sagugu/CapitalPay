"""Database helpers: PyMySQL as MySQLdb + shared MySQL DATABASES config."""
from __future__ import annotations

import os


def install_pymysql() -> None:
    """Register PyMySQL as MySQLdb so Django's mysql backend can import it."""
    try:
        import pymysql
    except ImportError:
        return
    pymysql.install_as_MySQLdb()


def mysql_databases_config(*, required: bool = False) -> dict | None:
    """
    Build Django DATABASES['default'] for MySQL 8.0 (utf8mb4).

    When required=False and MYSQL_HOST is empty, returns None (caller keeps SQLite).
    When required=True, missing/placeholder values raise RuntimeError.
    """

    def _required(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value or value.startswith("REPLACE_"):
            raise RuntimeError(f"Set {name} for the production MySQL 8.0 database")
        return value

    if required:
        host = _required("MYSQL_HOST")
        name = _required("MYSQL_DATABASE")
        user = _required("MYSQL_USER")
        password = _required("MYSQL_PASSWORD")
        default_ssl = "PREFERRED"
    else:
        host = os.environ.get("MYSQL_HOST", "").strip()
        if not host:
            return None
        name = os.environ.get("MYSQL_DATABASE", "b2b_payment").strip() or "b2b_payment"
        user = os.environ.get("MYSQL_USER", "b2b_payment").strip() or "b2b_payment"
        password = os.environ.get("MYSQL_PASSWORD", "").strip()
        default_ssl = "DISABLED"

    port = os.environ.get("MYSQL_PORT", "3306").strip() or "3306"
    conn_max_age = int(os.environ.get("MYSQL_CONN_MAX_AGE", "60"))
    ssl_mode = os.environ.get("MYSQL_SSL_MODE", default_ssl).strip().upper()

    options: dict = {
        "charset": "utf8mb4",
        "init_command": (
            "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION',"
            " NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"
        ),
    }
    if ssl_mode in ("DISABLED", "DISABLE", "FALSE", "0", "OFF"):
        options["ssl_disabled"] = True
    elif ssl_mode in ("REQUIRED", "REQUIRE", "VERIFY_CA", "VERIFY_IDENTITY"):
        # Empty ssl dict enables TLS; CA verification can be added via env later.
        options["ssl"] = {}
    # PREFERRED: omit ssl flags and let the server/client negotiate

    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": conn_max_age,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }
