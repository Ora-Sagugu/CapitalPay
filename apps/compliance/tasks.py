"""Scheduled compliance tasks."""
import logging

from django.core.management import call_command

logger = logging.getLogger(__name__)


def refresh_sanction_lists():
    """Download and merge the latest official OFAC/UN sanctions lists."""
    try:
        call_command("import_all_sanctions", download=True)
        logger.info("Sanctions lists refreshed from official sources")
        return "ok"
    except Exception:
        logger.exception("Sanctions list refresh failed")
        raise
