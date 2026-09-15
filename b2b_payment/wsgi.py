"""WSGI config for b2b_payment project."""
import os

from b2b_payment.db import install_pymysql

install_pymysql()

from django.core.wsgi import get_wsgi_application

# Production sets DJANGO_SETTINGS_MODULE via systemd EnvironmentFile.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "b2b_payment.settings.local")
application = get_wsgi_application()
