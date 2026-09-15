"""MySQL settings helper unit tests (no live database required)."""
import os
from unittest import TestCase

from b2b_payment.db import mysql_databases_config


class MysqlDatabasesConfigTests(TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in list(os.environ)
            if key.startswith("MYSQL_")
        }
        for key in list(os.environ):
            if key.startswith("MYSQL_"):
                del os.environ[key]

    def tearDown(self):
        for key in list(os.environ):
            if key.startswith("MYSQL_"):
                del os.environ[key]
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_optional_without_host_returns_none(self):
        self.assertIsNone(mysql_databases_config(required=False))

    def test_optional_with_host_builds_mysql_config(self):
        os.environ["MYSQL_HOST"] = "127.0.0.1"
        os.environ["MYSQL_DATABASE"] = "b2b_payment"
        os.environ["MYSQL_USER"] = "b2b_payment"
        os.environ["MYSQL_PASSWORD"] = "secret"
        os.environ["MYSQL_SSL_MODE"] = "DISABLED"
        cfg = mysql_databases_config(required=False)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(cfg["PORT"], "3306")
        self.assertEqual(cfg["OPTIONS"]["charset"], "utf8mb4")
        self.assertTrue(cfg["OPTIONS"]["ssl_disabled"])
        self.assertIn("STRICT_TRANS_TABLES", cfg["OPTIONS"]["init_command"])

    def test_required_missing_host_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            mysql_databases_config(required=True)
        self.assertIn("MYSQL_HOST", str(ctx.exception))

    def test_required_rejects_placeholder_password(self):
        os.environ["MYSQL_HOST"] = "127.0.0.1"
        os.environ["MYSQL_DATABASE"] = "b2b_payment"
        os.environ["MYSQL_USER"] = "b2b_payment"
        os.environ["MYSQL_PASSWORD"] = "REPLACE_WITH_DATABASE_PASSWORD"
        with self.assertRaises(RuntimeError) as ctx:
            mysql_databases_config(required=True)
        self.assertIn("MYSQL_PASSWORD", str(ctx.exception))
