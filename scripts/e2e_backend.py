"""Start an isolated, seeded backend for Playwright end-to-end tests."""
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / ".run"
RUN_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "b2b_payment.settings.local")
os.environ["SQLITE_DATABASE"] = str(RUN_DIR / "e2e.sqlite3")
os.environ["BANK_GATEWAY_MODE"] = "MOCK"
os.environ["BANK_RECON_FETCH_MODE"] = "MOCK"
os.environ["BANK_FX_PROVIDER_MODE"] = "MOCK"
os.environ["SMS_PROVIDER_MODE"] = "MOCK"

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402


call_command("migrate", interactive=False, verbosity=0)
call_command("seed_data", reset=True, verbosity=0)
print("E2E_BACKEND_READY", flush=True)
call_command(
    "runserver",
    "127.0.0.1:1028",
    use_reloader=False,
    verbosity=1,
)
