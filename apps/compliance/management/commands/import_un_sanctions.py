"""
管理命令：导入联合国安理会综合制裁名单

用法：
    # 从官方 XML 下载少量测试数据（默认 30 条）
    python manage.py import_un_sanctions --download --reset

    # 指定条数
    python manage.py import_un_sanctions --download --max-entries 30 --reset

    # 从本地 HTML / XML 文件导入
    python manage.py import_un_sanctions --file path/to/consolidated.xml --reset

    # 试运行（不写入数据库）
    python manage.py import_un_sanctions --download --dry-run

数据来源：联合国安全理事会综合名单
https://scsanctions.un.org/resources/xml/en/consolidated.xml
"""

import io
import os
import re
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand, CommandError

from apps.compliance.country_names import guess_country_from_text, normalize_country_display
from apps.compliance.models import SanctionHitDetail, SanctionList

UN_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,*/*",
}
DEFAULT_DOWNLOAD_LIMIT = 0


# ── 委员会/制裁项目映射 ─────────────────────────────────────
COMMITTEE_MAP: Dict[str, Dict[str, str]] = {
    "QDi": {"program": "Al-Qaida/ISIL (1267/1989/2253)", "country": "Multiple"},
    "TAi": {"program": "Taliban (1988)", "country": "Afghanistan"},
    "KPi": {"program": "North Korea (1718)", "country": "North Korea"},
    "IQi": {"program": "Iraq (1518)", "country": "Iraq"},
    "CDi": {"program": "DR Congo (1533)", "country": "DR Congo"},
    "IRi": {"program": "Iran (1737)", "country": "Iran"},
    "LYi": {"program": "Libya (1970)", "country": "Libya"},
    "SOi": {"program": "Somalia (751)", "country": "Somalia"},
    "CFi": {"program": "Central African Republic (2127)", "country": "Central African Republic"},
    "SDi": {"program": "Sudan (1591)", "country": "Sudan"},
    "HTi": {"program": "Haiti (2653)", "country": "Haiti"},
    "YEi": {"program": "Yemen (2140)", "country": "Yemen"},
    "GBi": {"program": "Guinea-Bissau (2048)", "country": "Guinea-Bissau"},
    "SSi": {"program": "South Sudan (2206)", "country": "South Sudan"},
    "QDe": {"program": "Al-Qaida/ISIL (1267/1989/2253)", "country": "Multiple"},
    "TAe": {"program": "Taliban (1988)", "country": "Afghanistan"},
    "KPe": {"program": "North Korea (1718)", "country": "North Korea"},
    "IQe": {"program": "Iraq (1518)", "country": "Iraq"},
    "CDe": {"program": "DR Congo (1533)", "country": "DR Congo"},
    "IRe": {"program": "Iran (1737)", "country": "Iran"},
    "LYe": {"program": "Libya (1970)", "country": "Libya"},
    "SOe": {"program": "Somalia (751)", "country": "Somalia"},
    "CFe": {"program": "Central African Republic (2127)", "country": "Central African Republic"},
    "HTe": {"program": "Haiti (2653)", "country": "Haiti"},
    "YEe": {"program": "Yemen (2140)", "country": "Yemen"},
}

# 个人记录中，名称字段之后可能出现的下一个字段名（用于截断名称提取）
IND_NAME_END_MARKERS = [
    "名称（原语文字):", "职称:", "头衔:", "出生日期:", "出生地点:",
    "足够确认身份的别名:", "不足确认身份的别名:",
    "国籍:", "护照编号:", "国内身份证编号:",
    "地址:", "列入名单日期:", "其他信息:",
]

# 实体记录中，名称字段之后可能出现的下一个字段名
ENT_NAME_END_MARKERS = [
    "名称（原语文字):", "别名:", "又称:", "地址:", "列入名单日期:", "其他信息:",
]


# ── 字段定义 ────────────────────────────────────────────────
INDIVIDUAL_FIELDS = [
    "职称", "头衔", "出生日期", "出生地点",
    "足够确认身份的别名", "不足确认身份的别名",
    "国籍", "护照编号", "国内身份证编号",
    "地址", "列入名单日期", "其他信息",
]

ENTITY_FIELDS = [
    "别名", "又称", "地址", "列入名单日期", "其他信息",
]


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def download_un_xml(timeout: int = 120) -> bytes:
    """Download the official UN consolidated sanctions XML (follows 302)."""
    import requests

    resp = requests.get(
        UN_XML_URL,
        headers=DOWNLOAD_HEADERS,
        timeout=timeout,
        allow_redirects=True,
    )
    resp.raise_for_status()
    if len(resp.content) < 200:
        raise RuntimeError("UN XML response is empty")
    return resp.content


def _direct_text(parent: ET.Element, tag_name: str) -> str:
    want = tag_name.upper()
    for child in parent:
        if _local_tag(child.tag).upper() == want:
            return (child.text or "").strip()
    return ""


def _collect_values(parent: ET.Element, wrapper_tag: str) -> List[str]:
    values: List[str] = []
    want = wrapper_tag.upper()
    for child in parent:
        if _local_tag(child.tag).upper() != want:
            continue
        found = False
        for nested in child:
            if _local_tag(nested.tag).upper() == "VALUE":
                text = (nested.text or "").strip()
                if text:
                    values.append(text)
                    found = True
        if not found:
            text = (child.text or "").strip()
            if text:
                values.append(text)
    return values


def _join_address(addr_elem: ET.Element) -> str:
    parts = []
    for tag in ("STREET", "CITY", "STATE_PROVINCE", "ZIP_CODE", "COUNTRY"):
        val = _direct_text(addr_elem, tag)
        if val:
            parts.append(val)
    return ", ".join(parts)


def _parse_un_listed_date(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})",
        raw,
        re.IGNORECASE,
    )
    if m:
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        mo = months.get(m.group(2).lower()[:3])
        if mo:
            return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"
    return None


def _sample_diverse(records: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if not limit or limit >= len(records):
        return records
    groups: Dict[str, deque] = defaultdict(deque)
    for rec in records:
        ref = rec.get("reference_id") or ""
        prefix = ref.split(".", 1)[0] if "." in ref else "other"
        groups[prefix].append(rec)
    picked: List[Dict[str, Any]] = []
    while len(picked) < limit and groups:
        empty = []
        for prefix in list(groups.keys()):
            if len(picked) >= limit:
                break
            queue = groups[prefix]
            if queue:
                picked.append(queue.popleft())
            if not queue:
                empty.append(prefix)
        for prefix in empty:
            del groups[prefix]
    return picked


def _parse_un_individual_xml(elem: ET.Element) -> Optional[Dict[str, Any]]:
    ref_id = _direct_text(elem, "REFERENCE_NUMBER")
    first = _direct_text(elem, "FIRST_NAME")
    second = _direct_text(elem, "SECOND_NAME")
    third = _direct_text(elem, "THIRD_NAME")
    fourth = _direct_text(elem, "FOURTH_NAME")
    parts = [p for p in (first, second, third, fourth) if p and p.lower() not in ("na", "n/a")]
    full_name = " ".join(parts).strip()
    if not full_name and not ref_id:
        return None

    prefix = ref_id.split(".", 1)[0] if "." in ref_id else ""
    program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix or 'list'}")
    risk = "HIGH" if prefix in ("QDi", "QDe", "TAi", "TAe", "KPi", "KPe") else "MEDIUM"

    aliases = []
    for child in elem:
        if _local_tag(child.tag).upper() == "INDIVIDUAL_ALIAS":
            alias = _direct_text(child, "ALIAS_NAME")
            if alias:
                aliases.append(alias)

    nationality_vals = _collect_values(elem, "NATIONALITY")
    nationality = ", ".join(nationality_vals)

    addresses = []
    country = COMMITTEE_MAP.get(prefix, {}).get("country", "")
    for child in elem:
        if _local_tag(child.tag).upper() == "INDIVIDUAL_ADDRESS":
            addr = _join_address(child)
            if addr:
                addresses.append(addr)
            addr_country = _direct_text(child, "COUNTRY")
            if addr_country:
                country = addr_country
    if nationality_vals and not country:
        country = nationality_vals[0]

    dobs = []
    for child in elem:
        if _local_tag(child.tag).upper() == "INDIVIDUAL_DATE_OF_BIRTH":
            dob = _direct_text(child, "DATE") or _direct_text(child, "YEAR")
            if dob:
                dobs.append(dob)

    pobs = []
    for child in elem:
        if _local_tag(child.tag).upper() == "INDIVIDUAL_PLACE_OF_BIRTH":
            pob = _join_address(child) or _direct_text(child, "CITY")
            if pob:
                pobs.append(pob)

    id_parts = []
    for child in elem:
        if _local_tag(child.tag).upper() == "INDIVIDUAL_DOCUMENT":
            doc_type = _direct_text(child, "TYPE_OF_DOCUMENT") or "ID"
            number = _direct_text(child, "NUMBER")
            if number:
                id_parts.append(f"{doc_type}: {number}")

    comments = _direct_text(elem, "COMMENTS1")
    listed_on = _parse_un_listed_date(_direct_text(elem, "LISTED_ON"))

    return {
        "entity_type": "INDIVIDUAL",
        "entity_name": full_name or ref_id,
        "reference_id": ref_id,
        "aliases": ", ".join(aliases)[:500],
        "country": normalize_country_display(country)[:64],
        "nationality": nationality[:64],
        "date_of_birth": (dobs[0] if dobs else "")[:64],
        "place_of_birth": (pobs[0] if pobs else "")[:256],
        "id_number": "; ".join(id_parts)[:256],
        "address": "; ".join(addresses)[:1000],
        "sanction_reason": f"[{program}] {comments}"[:500],
        "risk_level": risk,
        "listed_date": listed_on,
    }


def _parse_un_entity_xml(elem: ET.Element) -> Optional[Dict[str, Any]]:
    ref_id = _direct_text(elem, "REFERENCE_NUMBER")
    name = _direct_text(elem, "FIRST_NAME") or _direct_text(elem, "NAME")
    if not name and not ref_id:
        return None

    prefix = ref_id.split(".", 1)[0] if "." in ref_id else ""
    program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix or 'list'}")
    risk = "HIGH" if prefix in ("QDe", "TAe", "KPe") else "MEDIUM"

    aliases = []
    for child in elem:
        if _local_tag(child.tag).upper() == "ENTITY_ALIAS":
            alias = _direct_text(child, "ALIAS_NAME")
            if alias:
                aliases.append(alias)

    addresses = []
    country = COMMITTEE_MAP.get(prefix, {}).get("country", "")
    for child in elem:
        if _local_tag(child.tag).upper() == "ENTITY_ADDRESS":
            addr = _join_address(child)
            if addr:
                addresses.append(addr)
            addr_country = _direct_text(child, "COUNTRY")
            if addr_country:
                country = addr_country

    comments = _direct_text(elem, "COMMENTS1")
    listed_on = _parse_un_listed_date(_direct_text(elem, "LISTED_ON"))

    return {
        "entity_type": "ORGANIZATION",
        "entity_name": name or ref_id,
        "reference_id": ref_id,
        "aliases": ", ".join(aliases)[:500],
        "country": normalize_country_display(country)[:64],
        "nationality": "",
        "date_of_birth": None,
        "place_of_birth": "",
        "id_number": "",
        "address": "; ".join(addresses)[:1000],
        "sanction_reason": f"[{program}] {comments}"[:500],
        "risk_level": risk,
        "listed_date": listed_on,
    }


def parse_un_xml(xml_bytes: bytes, max_entries: Optional[int] = None) -> List[Dict[str, Any]]:
    """Parse official UN consolidated.xml into SanctionList-ready dicts."""
    root = ET.parse(io.BytesIO(xml_bytes)).getroot()
    individuals: List[Dict[str, Any]] = []
    entities: List[Dict[str, Any]] = []
    for elem in root.iter():
        tag = _local_tag(elem.tag).upper()
        if tag == "INDIVIDUAL":
            rec = _parse_un_individual_xml(elem)
            if rec and rec.get("entity_name"):
                individuals.append(rec)
        elif tag == "ENTITY":
            rec = _parse_un_entity_xml(elem)
            if rec and rec.get("entity_name"):
                entities.append(rec)

    if not max_entries:
        return individuals + entities

    n_ind = min(len(individuals), max(1, max_entries // 2))
    n_ent = min(len(entities), max_entries - n_ind)
    if n_ind + n_ent < max_entries:
        extra_ind = min(len(individuals) - n_ind, max_entries - n_ind - n_ent)
        n_ind += max(0, extra_ind)
        extra_ent = min(len(entities) - n_ent, max_entries - n_ind - n_ent)
        n_ent += max(0, extra_ent)

    return _sample_diverse(individuals, n_ind) + _sample_diverse(entities, n_ent)


def write_un_records(records: List[Dict[str, Any]]) -> tuple:
    created = 0
    skipped = 0
    for rec in records:
        try:
            eff_date = None
            listed = rec.get("listed_date")
            if listed and re.match(r"\d{4}-\d{2}-\d{2}", str(listed)):
                try:
                    eff_date = datetime.strptime(listed, "%Y-%m-%d").date()
                except ValueError:
                    pass
            SanctionList.objects.create(
                list_type="UN",
                entity_type=rec["entity_type"],
                entity_name=rec["entity_name"][:256],
                reference_id=(rec.get("reference_id") or "")[:32],
                alias_names=rec.get("aliases") or rec.get("alias_names") or "",
                country=normalize_country_display(rec.get("country") or ""),
                nationality=rec.get("nationality") or "",
                date_of_birth=rec.get("date_of_birth") or "",
                place_of_birth=rec.get("place_of_birth") or "",
                id_number=rec.get("id_number") or "",
                address=rec.get("address") or "",
                sanction_reason=rec.get("sanction_reason") or "",
                risk_level=rec.get("risk_level") or "HIGH",
                effective_date=eff_date,
                is_active=True,
            )
            created += 1
        except Exception:
            skipped += 1
    return created, skipped


def clear_un_data() -> tuple:
    hit_deleted, _ = SanctionHitDetail.objects.filter(sanction_entry__list_type="UN").delete()
    deleted, _ = SanctionList.objects.filter(list_type="UN").delete()
    return hit_deleted, deleted


class Command(BaseCommand):
    help = "导入联合国安理会综合制裁名单（官方 XML 或本地 HTML）"

    def add_arguments(self, parser):
        parser.add_argument("--download", action="store_true", default=False,
                            help="从联合国官网下载 consolidated.xml")
        parser.add_argument("--file", type=str, default=None,
                            help="本地 HTML 或 XML 文件路径")
        parser.add_argument("--max-entries", type=int, default=None, metavar="N",
                            help="最大导入条数（--download 时默认全部；可用 N 做抽样测试）")
        parser.add_argument("--reset", action="store_true", default=False,
                            help="导入前清空所有 UN 数据")
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help="只解析不写入数据库")

    def handle(self, *args, **options):
        download = options["download"]
        file_path = options["file"]
        max_entries = options["max_entries"]
        reset = options["reset"]
        dry_run = options["dry_run"]

        if download:
            if max_entries is None:
                max_entries = DEFAULT_DOWNLOAD_LIMIT
            self.stdout.write(self.style.MIGRATE_HEADING(
                "\n正在从联合国官网下载综合制裁名单 XML ..."
            ))
            self.stdout.write(f"   URL: {UN_XML_URL}")
            try:
                xml_bytes = download_un_xml()
            except Exception as exc:
                raise CommandError(f"联合国名单下载失败: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"   下载成功，{len(xml_bytes):,} bytes"))
            all_records = parse_un_xml(xml_bytes, max_entries=max_entries)
            limit_label = "all" if not max_entries else str(max_entries)
            self.stdout.write(f"   解析后保留 {len(all_records)} 条（上限 {limit_label}）")
        else:
            if not file_path:
                file_path = os.path.expanduser("~/Downloads/consolidatedLegacyByNAME.html")
            if not os.path.exists(file_path):
                raise CommandError(
                    f"文件不存在: {file_path}\n"
                    "请使用 --download 从官网拉取，或用 --file 指定本地 HTML/XML。"
                )
            self.stdout.write(f"读取文件: {file_path}")
            lower = file_path.lower()
            if lower.endswith(".xml"):
                with open(file_path, "rb") as f:
                    xml_bytes = f.read()
                self.stdout.write(f"文件大小: {len(xml_bytes):,} 字节")
                all_records = parse_un_xml(xml_bytes, max_entries=max_entries)
            else:
                all_records = self._parse_html_file(file_path)
                if max_entries:
                    persons = [r for r in all_records if r["entity_type"] == "INDIVIDUAL"]
                    companies = [r for r in all_records if r["entity_type"] != "INDIVIDUAL"]
                    n_ind = min(len(persons), max(1, max_entries // 2))
                    n_ent = min(len(companies), max_entries - n_ind)
                    all_records = _sample_diverse(persons, n_ind) + _sample_diverse(companies, n_ent)

        empty_names = sum(1 for r in all_records if not r["entity_name"])
        if empty_names:
            self.stderr.write(f"警告: {empty_names} 条记录名称为空")

        self.stdout.write(f"\n总计: {len(all_records)} 条制裁记录")
        if dry_run:
            self._print_summary(all_records)
            return

        self.stdout.write("\n写入数据库...")
        if reset:
            hit_deleted, deleted = clear_un_data()
            if hit_deleted:
                self.stdout.write(f"  已清除 {hit_deleted} 条关联命中明细")
            self.stdout.write(f"  已清除 {deleted} 条旧 UN 数据")

        created, skipped = write_un_records(all_records)
        self.stdout.write(
            self.style.SUCCESS(f"  导入完成: 新增 {created} 条, 跳过 {skipped} 条")
        )
        self._print_summary(all_records)

    def _parse_html_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise CommandError(
                "解析 HTML 需要 beautifulsoup4。请改用 --download 导入官方 XML，"
                "或 pip install beautifulsoup4 后再导入 HTML。"
            ) from exc

        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.stdout.write(f"文件大小: {len(html_content):,} 字节")

        soup = BeautifulSoup(html_content, "html.parser")

        for p in soup.find_all("p"):
            if "文件生成日期" in p.get_text():
                self.stdout.write(f"  {p.get_text().strip()[:80]}")
                break

        tables = soup.find_all("table", id="sanctions")
        if not tables:
            raise CommandError("未找到制裁名单表格")

        self.stdout.write("\n解析个人记录...")
        individual_records = self._parse_table(tables[0], "INDIVIDUAL")
        self.stdout.write(f"  个人: {len(individual_records)} 条")

        entity_records = []
        if len(tables) > 1:
            self.stdout.write("\n解析实体记录...")
            entity_records = self._parse_table(tables[1], "ORGANIZATION")
            self.stdout.write(f"  实体: {len(entity_records)} 条")

        return individual_records + entity_records

    # ── 核心解析方法 ─────────────────────────────────────────

    def _parse_table(self, table, entity_type: str) -> List[Dict[str, Any]]:
        records = []
        rows = table.find_all("tr", class_="rowtext")
        for row in rows:
            td = row.find("td")
            if not td:
                continue
            text = td.get_text(" ", strip=True)
            rec = self._parse_individual(text) if entity_type == "INDIVIDUAL" else self._parse_entity(text)
            if rec:
                records.append(rec)
        return records

    def _parse_individual(self, text: str) -> Optional[Dict[str, Any]]:
        m = re.match(r'([A-Z]{2,4})i\.(\d+)', text)
        if not m:
            return None
        prefix, num = m.group(1), m.group(2)
        ref_id = f"{prefix}i.{num}"

        clean = self._normalize(text)

        # 提取名称
        name_raw = self._extract_until(clean, "名称:", IND_NAME_END_MARKERS) or ""
        full_name = self._build_name_from_parts(name_raw)

        # 提取字段
        fields = self._extract_all_fields(clean, INDIVIDUAL_FIELDS)

        nationality = self._clean(fields.get("国籍", ""))
        country = self._guess_country(clean, nationality) or COMMITTEE_MAP.get(prefix, {}).get("country", "")

        dob = self._clean(fields.get("出生日期", ""))
        if dob in ("无", "", "约"):
            dob = None
        elif dob:
            dob = self._parse_date(dob) or dob[:50]

        reason = self._clean(fields.get("其他信息", ""))
        if len(reason) > 500:
            reason = reason[:497] + "..."

        program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix}")
        risk = "HIGH" if prefix in ("QDi", "QDe", "TAi", "TAe", "KPi", "KPe") else "MEDIUM"

        return {
            "entity_type": "INDIVIDUAL",
            "entity_name": full_name,
            "reference_id": ref_id,
            "aliases": self._clean(fields.get("足够确认身份的别名", "")),
            "country": country,
            "nationality": nationality,
            "date_of_birth": dob,
            "place_of_birth": self._clean(fields.get("出生地点", "")),
            "id_number": self._build_id_number(fields),
            "address": self._clean(fields.get("地址", "")),
            "sanction_reason": f"[{program}] {reason}"[:500],
            "risk_level": risk,
            "listed_date": self._parse_date(self._clean(fields.get("列入名单日期", ""))),
        }

    def _parse_entity(self, text: str) -> Optional[Dict[str, Any]]:
        m = re.match(r'([A-Z]{2,4})e\.(\d+)', text)
        if not m:
            return None
        prefix, num = m.group(1), m.group(2)
        ref_id = f"{prefix}e.{num}"

        clean = self._normalize(text)

        # 提取名称
        entity_name = self._extract_until(clean, "名称:", ENT_NAME_END_MARKERS) or ""

        fields = self._extract_all_fields(clean, ENTITY_FIELDS)

        aliases = self._clean(fields.get("别名", ""))
        reason = self._clean(fields.get("其他信息", ""))
        if len(reason) > 500:
            reason = reason[:497] + "..."

        program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix}")
        risk = "HIGH" if prefix in ("QDi", "QDe", "TAi", "TAe", "KPi", "KPe") else "MEDIUM"

        return {
            "entity_type": "ORGANIZATION",
            "entity_name": entity_name,
            "reference_id": ref_id,
            "aliases": aliases,
            "country": COMMITTEE_MAP.get(prefix, {}).get("country", ""),
            "nationality": "",
            "date_of_birth": None,
            "place_of_birth": "",
            "id_number": "",
            "address": self._clean(fields.get("地址", "")),
            "sanction_reason": f"[{program}] {reason}"[:500],
            "risk_level": risk,
            "listed_date": self._parse_date(self._clean(fields.get("列入名单日期", ""))),
        }

    # ── 辅助方法 ──────────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        """标准化文本"""
        t = re.sub(r'<[^>]+>', ' ', text)
        t = re.sub(r'&nbsp;', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    def _extract_until(self, text: str, field_start: str, end_markers: List[str]) -> Optional[str]:
        """从 field_start 之后提取内容，直到遇到 end_marker 为止"""
        idx = text.find(field_start)
        if idx == -1:
            return None
        start = idx + len(field_start)
        end = len(text)
        for marker in end_markers:
            pos = text.find(marker, start)
            if pos != -1 and pos < end:
                end = pos
        return text[start:end].strip()

    def _extract_all_fields(self, text: str, field_names: List[str]) -> Dict[str, str]:
        """从格式化文本中提取所有字段值"""
        result = {}
        for i, fn in enumerate(field_names):
            next_fn = field_names[i + 1] if i + 1 < len(field_names) else "___END___"
            pat = re.escape(fn) + r":\s*(.*?)(?=\s*" + re.escape(next_fn) + r":|\s*$)"
            m = re.search(pat, text, re.DOTALL)
            if m:
                result[fn] = m.group(1).strip()
            else:
                result[fn] = ""
        return result

    def _build_name_from_parts(self, name_str: str) -> str:
        """从 1:LAST 2:FIRST 3:MIDDLE 4:SUFFIX 格式构建全名"""
        if not name_str:
            return ""

        parts = {"1": "", "2": "", "3": "", "4": ""}
        # 逐个提取每个 part，以 "无" 或其他 part 号为边界
        for key in ["1", "2", "3", "4"]:
            next_keys = [k for k in ["1", "2", "3", "4"] if k > key]
            if next_keys:
                pat = re.escape(key) + r":\s*(.+?)\s*(?=" + "|".join(re.escape(k) + ":" for k in next_keys) + r")"
            else:
                pat = re.escape(key) + r":\s*(.+)"
            m = re.search(pat, name_str)
            if m:
                val = m.group(1).strip()
                if val and val != "无":
                    parts[key] = val

        # 构建: FIRST MIDDLE LAST
        name_parts = []
        for k in ["2", "3", "1", "4"]:
            if parts[k]:
                name_parts.append(parts[k])

        return " ".join(name_parts) if name_parts else name_str

    def _clean(self, value: str) -> str:
        if not value:
            return ""
        value = re.sub(r'\s+', ' ', value).strip()
        return "" if value == "无" else value

    def _build_id_number(self, fields: Dict[str, str]) -> str:
        """合并护照编号和国内身份证编号"""
        parts = []
        passport = self._clean(fields.get("护照编号", ""))
        national_id = self._clean(fields.get("国内身份证编号", ""))
        if passport:
            parts.append(f"护照: {passport}")
        if national_id:
            parts.append(f"身份证: {national_id}")
        return "; ".join(parts)

    def _guess_country(self, text: str, nationality: str) -> str:
        return guess_country_from_text(nationality, text)

    def _parse_date(self, date_str: str) -> Optional[str]:
        if not date_str or date_str == "无":
            return None
        m = re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})', date_str, re.IGNORECASE)
        if m:
            months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
            mo = months.get(m.group(2).lower())
            if mo:
                try:
                    return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"
                except ValueError:
                    pass
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return date_str[:50] if date_str else None

    def _print_summary(self, records: List[Dict[str, Any]]):
        by_committee: Dict[str, int] = {}
        by_type: Dict[str, int] = {"INDIVIDUAL": 0, "ORGANIZATION": 0}
        empty_names = 0
        for r in records:
            ref = r["reference_id"]
            prefix = ref[:ref.rindex('.')]
            by_committee[prefix] = by_committee.get(prefix, 0) + 1
            by_type[r["entity_type"]] = by_type.get(r["entity_type"], 0) + 1
            if not r["entity_name"]:
                empty_names += 1

        self.stdout.write("\n按委员会分组:")
        for k, v in sorted(by_committee.items(), key=lambda x: -x[1]):
            info = COMMITTEE_MAP.get(k, {"program": k})
            self.stdout.write(f"  {k} ({info['program']}): {v} 条")
        if empty_names:
            self.stderr.write(f"\n空名称: {empty_names} 条")
        self.stdout.write(f"\n按类型: 个人={by_type.get('INDIVIDUAL',0)}, 实体={by_type.get('ORGANIZATION',0)}")
