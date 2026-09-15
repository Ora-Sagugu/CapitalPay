"""Import official OFAC SDN.CSV and UN consolidated.xml uploads."""
from xml.etree.ElementTree import ParseError

from django.conf import settings

from apps.compliance.country_names import normalize_country_display
from apps.compliance.models import SanctionHitDetail, SanctionList
from apps.core.exceptions import BusinessException

ALLOWED_LIST_TYPES = {"OFAC", "UN"}
MAX_IMPORT_BYTES = int(getattr(settings, "SANCTION_IMPORT_MAX_BYTES", 32 * 1024 * 1024))


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _file_extension(filename: str) -> str:
    name = (filename or "").rsplit(".", 1)
    if len(name) < 2:
        return ""
    return name[-1].lower()


def _read_upload(uploaded) -> bytes:
    if uploaded is None:
        raise BusinessException(
            "SANCTION_FILE_REQUIRED",
            "Select an official sanctions list file to import.",
        )
    size = getattr(uploaded, "size", None)
    if size == 0:
        raise BusinessException("SANCTION_FILE_EMPTY", "The uploaded file is empty.")
    if size and size > MAX_IMPORT_BYTES:
        raise BusinessException(
            "SANCTION_FILE_TOO_LARGE",
            "The file exceeds the 32 MB import limit.",
        )
    uploaded.seek(0)
    raw = uploaded.read()
    if not raw:
        raise BusinessException("SANCTION_FILE_EMPTY", "The uploaded file is empty.")
    if len(raw) > MAX_IMPORT_BYTES:
        raise BusinessException(
            "SANCTION_FILE_TOO_LARGE",
            "The file exceeds the 32 MB import limit.",
        )
    return raw


def _counts() -> dict:
    return {
        "total_ofac": SanctionList.objects.filter(list_type="OFAC", is_active=True).count(),
        "total_un": SanctionList.objects.filter(list_type="UN", is_active=True).count(),
        "total_all": SanctionList.objects.filter(is_active=True).count(),
    }


def clear_ofac_data() -> tuple:
    hit_deleted, _ = SanctionHitDetail.objects.filter(sanction_entry__list_type="OFAC").delete()
    deleted, _ = SanctionList.objects.filter(list_type="OFAC").delete()
    return hit_deleted, deleted


def _import_ofac(raw: bytes, reset: bool) -> int:
    from apps.compliance.management.commands.import_ofac_sdn import (
        decode_sdn_bytes,
        parse_sdn_csv_text,
    )

    if raw.lstrip().startswith(b"<"):
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "OFAC imports require the official SDN.CSV file, not XML.",
        )
    try:
        entries = parse_sdn_csv_text(decode_sdn_bytes(raw), max_entries=0)
    except Exception:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "The file is not a valid OFAC SDN.CSV.",
        )
    if not entries:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "The file is not a valid OFAC SDN.CSV, or it contains no listings.",
        )
    for entry in entries:
        entry.country = normalize_country_display(entry.country or "")[:64]
    if reset:
        clear_ofac_data()
    created = SanctionList.objects.bulk_create(entries, ignore_conflicts=True, batch_size=200)
    return len(created)


def _import_un(raw: bytes, reset: bool) -> int:
    from apps.compliance.management.commands.import_un_sanctions import (
        clear_un_data,
        parse_un_xml,
        write_un_records,
    )

    stripped = raw.lstrip()
    if not stripped.startswith(b"<") and b"<?xml" not in stripped[:200]:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "UN imports require the official consolidated.xml file.",
        )
    try:
        records = parse_un_xml(raw, max_entries=0)
    except ParseError:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "The file is not a valid UN consolidated.xml.",
        )
    except Exception:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "The file is not a valid UN consolidated.xml.",
        )
    if not records:
        raise BusinessException(
            "SANCTION_FILE_INVALID",
            "The file is not a valid UN consolidated.xml, or it contains no listings.",
        )
    if reset:
        clear_un_data()
    created, _skipped = write_un_records(records)
    return created


def import_official_file(*, uploaded, list_type: str, reset=False) -> dict:
    source = str(list_type or "").strip().upper()
    if source not in ALLOWED_LIST_TYPES:
        raise BusinessException(
            "SANCTION_LIST_TYPE_INVALID",
            "Select OFAC or UN as the list source.",
        )
    raw = _read_upload(uploaded)
    filename = getattr(uploaded, "name", "") or ""
    ext = _file_extension(filename)
    if source == "OFAC" and ext != "csv":
        raise BusinessException(
            "SANCTION_FILE_TYPE_INVALID",
            "OFAC imports accept only the official SDN.CSV file.",
        )
    if source == "UN" and ext != "xml":
        raise BusinessException(
            "SANCTION_FILE_TYPE_INVALID",
            "UN imports accept only the official consolidated.xml file.",
        )
    created = _import_ofac(raw, _truthy(reset)) if source == "OFAC" else _import_un(raw, _truthy(reset))
    return {"created": created, "list_type": source, **_counts()}
