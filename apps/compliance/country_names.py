"""Country name normalization — display English names in API/UI."""

# Chinese → English (also covers legacy imported values)
CN_TO_EN = {
    "多国": "Multiple",
    "阿富汗": "Afghanistan",
    "朝鲜": "North Korea",
    "北朝鲜": "North Korea",
    "伊拉克": "Iraq",
    "刚果民主共和国": "DR Congo",
    "刚果": "DR Congo",
    "伊朗": "Iran",
    "利比亚": "Libya",
    "索马里": "Somalia",
    "中非共和国": "Central African Republic",
    "中非": "Central African Republic",
    "苏丹": "Sudan",
    "海地": "Haiti",
    "也门": "Yemen",
    "几内亚比绍": "Guinea-Bissau",
    "南苏丹": "South Sudan",
    "俄罗斯联邦": "Russia",
    "俄罗斯": "Russia",
    "阿拉伯叙利亚共和国": "Syria",
    "叙利亚": "Syria",
    "阿尔及利亚": "Algeria",
    "巴基斯坦": "Pakistan",
    "沙特阿拉伯": "Saudi Arabia",
    "沙特": "Saudi Arabia",
    "尼日利亚": "Nigeria",
    "马里": "Mali",
    "法国": "France",
    "英国": "United Kingdom",
    "德国": "Germany",
    "意大利": "Italy",
    "哥伦比亚": "Colombia",
    "阿拉伯联合酋长国": "United Arab Emirates",
    "中国": "China",
    "日本": "Japan",
    "黎巴嫩": "Lebanon",
    "埃及": "Egypt",
    "摩洛哥": "Morocco",
    "突尼斯": "Tunisia",
    "卡塔尔": "Qatar",
    "科威特": "Kuwait",
    "土耳其": "Turkey",
    "印度": "India",
    "印度尼西亚": "Indonesia",
    "马来西亚": "Malaysia",
    "菲律宾": "Philippines",
    "泰国": "Thailand",
    "肯尼亚": "Kenya",
    "南非": "South Africa",
    "比利时": "Belgium",
    "荷兰": "Netherlands",
    "瑞士": "Switzerland",
    "奥地利": "Austria",
    "瑞典": "Sweden",
    "西班牙": "Spain",
    "希腊": "Greece",
    "乌克兰": "Ukraine",
    "白俄罗斯": "Belarus",
    "澳大利亚": "Australia",
    "加拿大": "Canada",
}

# English keyword → canonical English (for nationality / free-text guessing)
EN_KEYWORDS = {
    "afghanistan": "Afghanistan",
    "democratic republic of the congo": "DR Congo",
    "dr congo": "DR Congo",
    "congo": "DR Congo",
    "dprk": "North Korea",
    "north korea": "North Korea",
    "korea": "North Korea",
    "iraq": "Iraq",
    "iran": "Iran",
    "libya": "Libya",
    "somalia": "Somalia",
    "central african republic": "Central African Republic",
    "sudan": "Sudan",
    "haiti": "Haiti",
    "yemen": "Yemen",
    "guinea-bissau": "Guinea-Bissau",
    "south sudan": "South Sudan",
    "russia": "Russia",
    "syria": "Syria",
    "syrian": "Syria",
    "pakistan": "Pakistan",
    "saudi arabia": "Saudi Arabia",
    "nigeria": "Nigeria",
    "mali": "Mali",
    "france": "France",
    "united kingdom": "United Kingdom",
    "germany": "Germany",
    "italy": "Italy",
    "colombia": "Colombia",
    "china": "China",
    "japan": "Japan",
    "lebanon": "Lebanon",
    "egypt": "Egypt",
    "morocco": "Morocco",
    "tunisia": "Tunisia",
    "qatar": "Qatar",
    "kuwait": "Kuwait",
    "turkey": "Turkey",
    "india": "India",
    "indonesia": "Indonesia",
    "malaysia": "Malaysia",
    "philippines": "Philippines",
    "thailand": "Thailand",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "belgium": "Belgium",
    "netherlands": "Netherlands",
    "switzerland": "Switzerland",
    "austria": "Austria",
    "sweden": "Sweden",
    "spain": "Spain",
    "greece": "Greece",
    "ukraine": "Ukraine",
    "belarus": "Belarus",
    "australia": "Australia",
    "canada": "Canada",
    "united arab emirates": "United Arab Emirates",
    "uae": "United Arab Emirates",
    "multiple": "Multiple",
}


def normalize_country_display(country: str) -> str:
    """Return English country name for display; pass through unknown values."""
    value = (country or "").strip()
    if not value:
        return ""
    if value in CN_TO_EN:
        return CN_TO_EN[value]
    lower = value.lower()
    if lower in EN_KEYWORDS:
        return EN_KEYWORDS[lower]
    for kw, en in sorted(EN_KEYWORDS.items(), key=lambda item: -len(item[0])):
        if kw in lower:
            return en
    for cn, en in CN_TO_EN.items():
        if cn in value:
            return en
    return value


def guess_country_from_text(*texts: str) -> str:
    """Guess canonical English country from nationality / address / remarks."""
    combined = " ".join(t for t in texts if t).strip()
    if not combined:
        return ""
    normalized = normalize_country_display(combined)
    if normalized != combined:
        return normalized
    lower = combined.lower()
    for kw, en in sorted(EN_KEYWORDS.items(), key=lambda item: -len(item[0])):
        if kw in lower:
            return en
    for cn, en in CN_TO_EN.items():
        if cn in combined:
            return en
    return combined[:64]
