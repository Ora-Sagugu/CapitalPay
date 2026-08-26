"""WSGI config for b2b_payment project."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "b2b_payment.settings.local")
application = get_wsgi_application()
