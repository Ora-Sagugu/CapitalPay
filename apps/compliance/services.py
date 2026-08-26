"""Compliance services — 制裁扫描服务"""
import random
from datetime import datetime

# 常规业务运营所在国家，排除国家/地区匹配（防止误报）
# 这些国家虽有个别实体被制裁，但国家本身不是制裁对象
SAFE_HOST_COUNTRIES = frozenset([
    "china", "中国",
    "united states", "usa", "美国",
    "united kingdom", "uk", "英国",
    "france", "法国", "germany", "德国",
    "japan", "日本", "south korea", "韩国",
    "singapore", "新加坡", "hong kong", "香港",
])


# 通用地址停用词：极容易在任意地址中出现，不能作为制裁命中依据
# （避免把 "Main Street, Central District" 这类通用词误判为制裁实体）
# 同时排除全球主要通用城市名：仅因同处一座大城市（如 New York / London）
# 就命中制裁实体属于噪声，且会导致误拦截正常汇款。
ADDRESS_STOPWORDS = frozenset({
    "main", "street", "st", "road", "rd", "avenue", "ave", "boulevard", "blvd",
    "building", "bldg", "tower", "floor", "fl", "block", "district", "dist",
    "central", "park", "plaza", "square", "sq", "west", "east", "north", "south",
    "northern", "southern", "eastern", "western", "city", "town", "no", "number",
    "lane", "ln", "court", "ct", "highway", "hwy", "expressway", "the", "of", "and",
    "area", "zone", "region", "near", "next", "behind", "front", "inside", "outside",
    "unit", "suite", "ste", "room", "rm", "level", "flr", "po", "box",
    # 主要通用城市（国家/地区命中由 country 匹配单独处理）
    "london", "paris", "berlin", "rome", "madrid", "tokyo", "moscow", "kyiv", "kiev",
    "beijing", "shanghai", "hongkong", "hong", "dubai", "singapore", "toronto",
    "sydney", "mumbai", "delhi", "cairo", "lagos", "nairobi", "istanbul", "seoul",
    "bangkok", "jakarta", "manila", "saopaulo", "chicago", "boston", "losangeles",
    "sanfrancisco", "washington", "houston", "atlanta", "dallas", "miami", "seattle",
    "denver", "phoenix", "york", "newyork",
})


def generate_scan_no():
    now = datetime.now()
    rand_part = random.randint(10000, 99999)
    return f"SC{now.strftime('%Y%m%d%H%M%S')}{rand_part}"


def scan_entity(target_name, target_type="PERSON", target_id=""):
    """
    扫描实体是否命中制裁名单
    返回: (is_hit, hits_list)
    """
    from .models import SanctionList, SanctionScanRecord, SanctionHitDetail
    import difflib

    # 创建扫描记录
    scan_record = SanctionScanRecord.objects.create(
        scan_no=generate_scan_no(),
        scan_type="TRANSACTION",
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        status="SCANNING",
    )

    # 查询活跃制裁名单
    active_lists = SanctionList.objects.filter(is_active=True)
    hits = []

    for entry in active_lists:
        # 精确匹配
        if entry.entity_name.lower() == target_name.lower():
            hits.append((entry, 1.0, "entity_name"))
            continue
        # 别名匹配
        if entry.alias_names:
            aliases = [a.strip() for a in entry.alias_names.split(",")]
            alias_hit = False
            for alias in aliases:
                if alias.lower() == target_name.lower():
                    hits.append((entry, 1.0, "alias_name"))
                    alias_hit = True
                    break
            if alias_hit:
                continue
        # 模糊匹配 (>80%相似度)
        # 最短长度保护：过短的名称 (<=3) 过于歧义，仅允许精确/别名匹配
        if len(target_name) >= 4 and len(entry.entity_name) >= 4:
            similarity = _name_similarity(entry.entity_name.lower(), target_name.lower())
            if similarity >= 0.8:
                hits.append((entry, similarity, "entity_name_fuzzy"))

    scan_record.hit_count = len(hits)
    scan_record.status = "HIT" if hits else "CLEAR"
    scan_record.scan_result = {"hits_found": len(hits)}
    scan_record.save()

    # 创建命中明细
    for entry, score, field in hits:
        SanctionHitDetail.objects.create(
            scan_record=scan_record,
            sanction_entry=entry,
            match_field=field,
            match_value=target_name,
            match_score=score,
        )

    return scan_record.status == "CLEAR", scan_record


def scan_entity_lightweight(beneficiary_name: str, beneficiary_address: str = "") -> dict:
    """
    轻量级制裁预检（不创建扫描记录，直接返回命中结果）
    
    参数:
        beneficiary_name: 收款人/实体名称
        beneficiary_address: 收款人地址（用于关键字检测）
    
    返回:
        {
            "is_clear": bool,
            "name_hits": [{entity_name, list_type, risk_level, match_type, score, country, reason}],
            "address_hits": [{entity_name, list_type, risk_level, keyword, country}],
            "total_hits": int,
        }
    """
    from .models import SanctionList
    import difflib

    active_lists = SanctionList.objects.filter(is_active=True)
    name_hits = []
    address_hits = []

    if not beneficiary_name and not beneficiary_address:
        return {"is_clear": True, "name_hits": [], "address_hits": [], "total_hits": 0}

    name_lower = (beneficiary_name or "").strip().lower()
    address_lower = (beneficiary_address or "").strip().lower()

    # ── 姓名匹配 ──
    if name_lower:
        for entry in active_lists:
            matched = False

            # 精确匹配 entity_name
            if entry.entity_name.lower() == name_lower:
                name_hits.append({
                    "entity_name": entry.entity_name,
                    "list_type": entry.list_type,
                    "risk_level": entry.risk_level,
                    "match_type": "exact_name",
                    "score": 1.0,
                    "country": entry.country or "",
                    "reason": entry.sanction_reason or "",
                })
                matched = True

            # 别名精确匹配
            if not matched and entry.alias_names:
                aliases = [a.strip() for a in entry.alias_names.split(",")]
                for alias in aliases:
                    if alias.lower() == name_lower:
                        name_hits.append({
                            "entity_name": entry.entity_name,
                            "list_type": entry.list_type,
                            "risk_level": entry.risk_level,
                            "match_type": "alias_name",
                            "score": 1.0,
                            "country": entry.country or "",
                            "reason": entry.sanction_reason or "",
                        })
                        matched = True
                        break

            # 模糊匹配 (>80% 相似度)
            # 最短长度保护：过短名称 (<=3) 过于歧义，仅允许精确/别名匹配
            if not matched and len(name_lower) >= 4 and len(entry.entity_name) >= 4:
                similarity = _name_similarity(entry.entity_name.lower(), name_lower)
                if similarity >= 0.8:
                    name_hits.append({
                        "entity_name": entry.entity_name,
                        "list_type": entry.list_type,
                        "risk_level": entry.risk_level,
                        "match_type": "fuzzy_name",
                        "score": round(similarity, 4),
                        "country": entry.country or "",
                        "reason": entry.sanction_reason or "",
                    })

    # ── 地址关键字匹配 ──
    if address_lower:
        # 用提取的关键字在用户输入的地址中检测
        for entry in active_lists:
            # 方法1：地址包含匹配
            if entry.address and len(entry.address) > 3:
                if _address_contains(entry.address, address_lower):
                    address_hits.append({
                        "entity_name": entry.entity_name,
                        "list_type": entry.list_type,
                        "risk_level": entry.risk_level,
                        "keyword": entry.address[:80],
                        "country": entry.country or "",
                        "match_type": "address_contains",
                    })
                    continue

            # 方法2：国家/地区匹配
            if entry.country and len(entry.country) > 1:
                country_lower = entry.country.lower()
                # 排除常规业务所在国家（如 China）避免误报
                # 这些国家虽有个别实体被制裁，但国家本身不是制裁对象
                if country_lower in SAFE_HOST_COUNTRIES:
                    pass  # skip country match for safe host countries
                elif country_lower in address_lower:
                    # 避免 false positive（如 "China" 匹配 "chinatown"，需要词边界）
                    if _loose_word_match(country_lower, address_lower):
                        address_hits.append({
                            "entity_name": entry.entity_name,
                            "list_type": entry.list_type,
                            "risk_level": entry.risk_level,
                            "keyword": entry.country,
                            "country": entry.country or "",
                            "match_type": "country_match",
                        })

            # 方法3：地址关键词匹配
            if entry.address:
                keywords = _extract_address_keywords(entry.address)
                matched_keywords = [kw for kw in keywords if len(kw) >= 4 and kw in address_lower]
                if matched_keywords:
                    address_hits.append({
                        "entity_name": entry.entity_name,
                        "list_type": entry.list_type,
                        "risk_level": entry.risk_level,
                        "keyword": ", ".join(matched_keywords[:3]),
                        "country": entry.country or "",
                        "match_type": "address_keyword",
                    })

    # 去重：同一实体可能在 address_hits 中重复（多种匹配方式）
    seen_entities = set()
    unique_address_hits = []
    for hit in address_hits:
        key = hit["entity_name"] + hit.get("match_type", "")
        if key not in seen_entities:
            seen_entities.add(key)
            unique_address_hits.append(hit)

    # 去重：同一实体可能以 exact + fuzzy 多次命中（Bug 6），保留最高分的一条
    seen_names = set()
    unique_name_hits = []
    for hit in sorted(name_hits, key=lambda x: -x.get("score", 0)):
        if hit["entity_name"] not in seen_names:
            seen_names.add(hit["entity_name"])
            unique_name_hits.append(hit)
    name_hits = unique_name_hits

    total_hits = len(name_hits) + len(unique_address_hits)

    return {
        "is_clear": total_hits == 0,
        "name_hits": name_hits,
        "address_hits": unique_address_hits,
        "total_hits": total_hits,
    }


def _extract_address_keywords(address: str) -> list:
    """从地址中提取有意义的关键词（去除短词、数字、符号与通用地址词）"""
    import re
    if not address:
        return []
    # 按逗号、空格、换行分割
    parts = re.split(r'[,，\s\n]+', address.lower())
    keywords = []
    for p in parts:
        p = p.strip().strip('.,，。()（）/-')
        if len(p) < 5:
            continue
        if p.isdigit():
            continue
        # 纯数字+连字符（如 "44-46"）也排除
        if p.replace('-', '').isdigit():
            continue
        # 通用地址词（main/street/central...）不能作为制裁命中依据
        if p in ADDRESS_STOPWORDS:
            continue
        keywords.append(p)
    return keywords


def _address_contains(sanction_address: str, user_address: str) -> bool:
    """检查制裁地址中的关键片段是否包含在用户地址中"""
    # 取制裁地址的前两个有意义片段进行匹配
    keywords = _extract_address_keywords(sanction_address)
    match_count = 0
    for kw in keywords:
        if len(kw) >= 5 and kw in user_address:
            match_count += 1
    # 至少匹配 2 个关键词片段才认为命中
    return match_count >= 2


def _loose_word_match(keyword: str, text: str) -> bool:
    """宽松词匹配 — 要求关键字在文本中有词边界（前后为空格、标点、或首尾）

    词边界包含连字符与小数点，避免 "iran-tehran" / "u.s." 这类写法漏检。
    """
    import re
    # 使用词边界匹配，但允许关键字前后有标点和空格
    pattern = r'(?:^|[\s,，。、；;.\-])' + re.escape(keyword) + r'(?:$|[\s,，。、；;.\-])'
    return bool(re.search(pattern, text))


def _name_similarity(a: str, b: str) -> float:
    """姓名相似度 — token-set ratio。

    比单纯的 SequenceMatcher 更稳健：对词序敏感但能容忍别名/缩写，
    避免 "Ali" vs "Ala" 这类短串的误判（配合调用方的最短长度保护）。
    """
    import difflib
    a_tokens = sorted(set(a.split()))
    b_tokens = sorted(set(b.split()))
    if not a_tokens or not b_tokens:
        return 0.0
    a_sorted = " ".join(a_tokens)
    b_sorted = " ".join(b_tokens)
    base = difflib.SequenceMatcher(None, a_sorted, b_sorted).ratio()
    inter = set(a_tokens) & set(b_tokens)
    if inter:
        shorter = a_tokens if len(a_tokens) <= len(b_tokens) else b_tokens
        inter_str = " ".join(sorted(inter))
        inter_ratio = difflib.SequenceMatcher(
            None, inter_str, " ".join(shorter)
        ).ratio()
        return max(base, inter_ratio)
    return base
