"""High-risk sanctioned jurisdiction keywords (Iran, North Korea, etc.)."""
import re

SANCTIONED_JURISDICTIONS = (
    {
        "country": "Iran",
        "list_type": "OFAC/UN",
        "risk_level": "HIGH",
        "reason": "Comprehensive sanctions jurisdiction",
        "aliases": (
            "iran",
            "irani",
            "iranian",
            "islamic republic of iran",
            "伊朗",
        ),
    },
    {
        "country": "North Korea",
        "list_type": "OFAC/UN",
        "risk_level": "HIGH",
        "reason": "Comprehensive sanctions jurisdiction",
        "aliases": (
            "north korea",
            "dprk",
            "democratic people's republic of korea",
            "democratic peoples republic of korea",
            "朝鲜",
            "北朝鲜",
        ),
    },
)


def _loose_word_match(keyword: str, text: str) -> bool:
    pattern = (
        r'(?:^|[\s,，。、；;.\-])'
        + re.escape(keyword)
        + r'(?:$|[\s,，。、；;.\-])'
    )
    return bool(re.search(pattern, text))


def detect_sanctioned_country(text: str) -> list:
    """Return country-name hits for sanctioned jurisdictions in free text."""
    normalized = (text or "").strip().lower()
    if not normalized:
        return []

    hits = []
    seen = set()
    for entry in SANCTIONED_JURISDICTIONS:
        for alias in entry["aliases"]:
            alias_lower = alias.lower()
            if len(alias_lower) < 2:
                continue
            if alias_lower not in normalized and not _loose_word_match(alias_lower, normalized):
                continue
            key = (entry["country"], alias_lower)
            if key in seen:
                continue
            seen.add(key)
            hits.append({
                "match_type": "country_name",
                "country": entry["country"],
                "list_type": entry["list_type"],
                "risk_level": entry["risk_level"],
                "keyword": alias,
                "reason": entry["reason"],
            })
    return hits
