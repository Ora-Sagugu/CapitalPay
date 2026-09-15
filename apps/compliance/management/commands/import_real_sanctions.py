"""导入真实制裁名单数据 — 联合国 HTML (英文PRN版) + OFAC Enhanced XML

用法:
    python manage.py import_real_sanctions \\
        --un-file "C:/Users/admin/Downloads/consolidatedLegacyByPRN.html" \\
        --ofac-file "C:/Users/admin/Downloads/sdn_enhanced.zip" \\
        --reset

    # 仅导入联合国
    python manage.py import_real_sanctions --un-file path/to/file.html --reset --only-un

    # 仅导入OFAC
    python manage.py import_real_sanctions --ofac-file path/to/file.zip --reset --only-ofac

    # 试运行
    python manage.py import_real_sanctions --un-file ... --ofac-file ... --dry-run
"""
import os
import re
import zipfile
import tempfile
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any, Tuple
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.compliance.models import SanctionList, SanctionHitDetail
from apps.compliance.country_names import guess_country_from_text, normalize_country_display


# ═══════════════════════════════════════════════════════════
#  联合国制裁名单 — 委员会/国家映射
# ═══════════════════════════════════════════════════════════
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

# UN 个人字段
UN_IND_FIELDS = [
    "Title", "Designation", "DOB", "POB",
    "Good quality a.k.a.", "Low quality a.k.a.",
    "Nationality", "Passport", "National ID",
    "Address", "Listed on", "Other information",
]

# UN 实体字段
UN_ENT_FIELDS = [
    "A.k.a.", "F.k.a.", "Address", "Listed on", "Other information",
]


# ═══════════════════════════════════════════════════════════
#  OFAC entityType → 内部映射
# ═══════════════════════════════════════════════════════════
OFAC_TYPE_MAP = {
    "Individual": "INDIVIDUAL",
    "Entity": "ORGANIZATION",
    "Vessel": "ENTITY",
    "Aircraft": "ENTITY",
}


class Command(BaseCommand):
    help = "导入真实制裁名单: 联合国 HTML (英文PRN版) + OFAC Enhanced XML"

    def add_arguments(self, parser):
        parser.add_argument("--un-file", type=str, default=None,
                            help="联合国 HTML 文件路径 (consolidatedLegacyByPRN.html)")
        parser.add_argument("--ofac-file", type=str, default=None,
                            help="OFAC Enhanced XML 文件路径 (.zip 或 .xml)")
        parser.add_argument("--reset", action="store_true", default=False,
                            help="导入前清空对应的旧数据")
        parser.add_argument("--only-un", action="store_true", default=False,
                            help="仅导入联合国数据")
        parser.add_argument("--only-ofac", action="store_true", default=False,
                            help="仅导入 OFAC 数据")
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help="只解析不写入数据库")
        parser.add_argument("--max-ofac", type=int, default=0,
                            help="OFAC 最大导入条数 (0=全部)")

    def handle(self, *args, **options):
        un_file = options["un_file"]
        ofac_file = options["ofac_file"]
        reset = options["reset"]
        only_un = options["only_un"]
        only_ofac = options["only_ofac"]
        dry_run = options["dry_run"]
        max_ofac = options["max_ofac"]

        if not un_file and not ofac_file:
            self.stderr.write(self.style.ERROR(
                "请指定至少一个文件: --un-file 或 --ofac-file"
            ))
            return

        # ── 清空旧数据 ──
        if reset and not dry_run:
            self._clear_data(only_un, only_ofac)

        # ── 导入联合国 ──
        if un_file and not only_ofac:
            self._import_un(un_file, dry_run)

        # ── 导入 OFAC ──
        if ofac_file and not only_un:
            self._import_ofac(ofac_file, dry_run, max_ofac)

        # ── 汇总 ──
        self._print_stats()

    REVIEW_DAYS = {"HIGH": 30, "MEDIUM": 90, "LOW": 180}

    def _calc_review_date(self, risk_level: str) -> Optional[date]:
        days = self.REVIEW_DAYS.get(risk_level)
        return date.today() + timedelta(days=days) if days else None

    # ═════════════════════════════════════════════════════════
    #  清空数据
    # ═════════════════════════════════════════════════════════
    def _clear_data(self, only_un: bool, only_ofac: bool):
        types_to_clear = []
        if not only_ofac:
            types_to_clear.append("UN")
        if not only_un:
            types_to_clear.append("OFAC")

        for lt in types_to_clear:
            # 先删关联命中明细（PROTECT 外键）
            hit_deleted, _ = SanctionHitDetail.objects.filter(
                sanction_entry__list_type=lt
            ).delete()
            if hit_deleted:
                self.stdout.write(f"  清除 {lt} 关联命中明细: {hit_deleted} 条")
            deleted, _ = SanctionList.objects.filter(list_type=lt).delete()
            self.stdout.write(self.style.WARNING(
                f"  已清空 {lt} 旧数据: {deleted} 条"
            ))

    # ═════════════════════════════════════════════════════════
    #  联合国 HTML 导入
    # ═════════════════════════════════════════════════════════
    def _import_un(self, file_path: str, dry_run: bool):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'━' * 60}\n  联合国制裁名单导入 (英文PRN版)\n  文件: {file_path}\n{'━' * 60}"
        ))

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"文件不存在: {file_path}"))
            return

        from bs4 import BeautifulSoup

        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.stdout.write(f"  文件大小: {len(html):,} 字节")

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", id="sanctions")
        if not tables:
            self.stderr.write(self.style.ERROR("未找到 id='sanctions' 的表格"))
            return

        self.stdout.write(f"  找到 {len(tables)} 个制裁名单表格")

        all_records: List[SanctionList] = []

        # 表格1: 个人
        if len(tables) >= 1:
            self.stdout.write("\n  解析个人记录...")
            ind_records = self._parse_un_table(tables[0], "INDIVIDUAL")
            self.stdout.write(f"    个人: {len(ind_records)} 条")
            all_records.extend(ind_records)

        # 表格2: 实体
        if len(tables) >= 2:
            self.stdout.write("\n  解析实体记录...")
            ent_records = self._parse_un_table(tables[1], "ORGANIZATION")
            self.stdout.write(f"    实体: {len(ent_records)} 条")
            all_records.extend(ent_records)

        # 过滤空名
        all_records = [r for r in all_records if r.entity_name]
        self.stdout.write(f"\n  有效记录: {len(all_records)} 条")

        if dry_run:
            self._print_un_summary(all_records)
            return

        # 写入数据库
        self.stdout.write("\n  写入数据库...")
        created = SanctionList.objects.bulk_create(
            all_records, batch_size=500, ignore_conflicts=True
        )
        self.stdout.write(self.style.SUCCESS(
            f"  联合国导入完成: {len(all_records)} 条"
        ))

    def _parse_un_table(self, table, entity_type: str) -> List[SanctionList]:
        records = []
        rows = table.find_all("tr", class_="rowtext")
        for row in rows:
            td = row.find("td")
            if not td:
                continue
            text = td.get_text(" ", strip=True)
            if entity_type == "INDIVIDUAL":
                rec = self._parse_un_individual(text)
            else:
                rec = self._parse_un_entity(text)
            if rec:
                records.append(rec)
        return records

    def _parse_un_individual(self, text: str) -> Optional[SanctionList]:
        m = re.match(r'([A-Z]{2,4})i\.(\d+)', text)
        if not m:
            return None
        prefix, num = m.group(1), m.group(2)
        ref_id = f"{prefix}i.{num}"
        clean = self._normalize_text(text)

        # 提取名称: Name: 1:FIRST 2:LAST ...
        name_raw = self._extract_field(clean, "Name:", UN_IND_FIELDS)
        full_name = self._build_name(name_raw)

        fields = self._extract_all_fields(clean, UN_IND_FIELDS)

        nationality = self._clean_val(fields.get("Nationality", ""))
        country = COMMITTEE_MAP.get(prefix, {}).get("country", "")
        if nationality:
            country = self._guess_country(nationality) or country

        dob = self._clean_val(fields.get("DOB", ""))
        if dob and dob != "na":
            dob = self._parse_date_str(dob) or dob[:50]
        else:
            dob = ""

        passport = self._clean_val(fields.get("Passport", ""))
        national_id = self._clean_val(fields.get("National ID", ""))
        id_parts = []
        if passport:
            id_parts.append(f"Passport: {passport}")
        if national_id:
            id_parts.append(f"National ID: {national_id}")
        id_number = "; ".join(id_parts)

        good_akas = self._clean_val(fields.get("Good quality a.k.a.", ""))
        low_akas = self._clean_val(fields.get("Low quality a.k.a.", ""))
        aliases = ", ".join(p for p in [good_akas, low_akas] if p)

        reason = self._clean_val(fields.get("Other information", ""))
        program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix}")
        risk = "HIGH" if prefix in ("QDi", "QDe", "TAi", "TAe", "KPi", "KPe") else "MEDIUM"

        listed_on = self._parse_date_str(self._clean_val(fields.get("Listed on", "")))

        return SanctionList(
            list_type="UN",
            entity_type="INDIVIDUAL",
            entity_name=full_name or ref_id,
            reference_id=ref_id,
            alias_names=aliases[:500],
            country=normalize_country_display(country),
            nationality=nationality,
            date_of_birth=dob,
            place_of_birth=self._clean_val(fields.get("POB", "")),
            id_number=id_number[:256],
            address=self._clean_val(fields.get("Address", ""))[:1000],
            sanction_reason=f"[{program}] {reason}"[:500],
            risk_level=risk,
            effective_date=listed_on,
            review_date=self._calc_review_date(risk),
            is_active=True,
        )

    def _parse_un_entity(self, text: str) -> Optional[SanctionList]:
        m = re.match(r'([A-Z]{2,4})e\.(\d+)', text)
        if not m:
            return None
        prefix, num = m.group(1), m.group(2)
        ref_id = f"{prefix}e.{num}"
        clean = self._normalize_text(text)

        entity_name = self._extract_field(clean, "Name:", UN_ENT_FIELDS)
        fields = self._extract_all_fields(clean, UN_ENT_FIELDS)

        akas = self._clean_val(fields.get("A.k.a.", ""))
        fkas = self._clean_val(fields.get("F.k.a.", ""))
        aliases = ", ".join(p for p in [akas, fkas] if p)

        reason = self._clean_val(fields.get("Other information", ""))
        program = COMMITTEE_MAP.get(prefix, {}).get("program", f"UN {prefix}")
        risk = "HIGH" if prefix in ("QDe", "TAe", "KPe") else "MEDIUM"
        listed_on = self._parse_date_str(self._clean_val(fields.get("Listed on", "")))

        return SanctionList(
            list_type="UN",
            entity_type="ORGANIZATION",
            entity_name=entity_name or ref_id,
            reference_id=ref_id,
            alias_names=aliases[:500],
            country=normalize_country_display(COMMITTEE_MAP.get(prefix, {}).get("country", "")),
            nationality="",
            date_of_birth="",
            place_of_birth="",
            id_number="",
            address=self._clean_val(fields.get("Address", ""))[:1000],
            sanction_reason=f"[{program}] {reason}"[:500],
            risk_level=risk,
            effective_date=listed_on,
            review_date=self._calc_review_date(risk),
            is_active=True,
        )

    # ── UN 辅助方法 ──

    def _normalize_text(self, text: str) -> str:
        t = re.sub(r'<[^>]+>', ' ', text)
        t = re.sub(r'&nbsp;', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    def _extract_field(self, text: str, field_start: str, end_fields: List[str]) -> str:
        idx = text.find(field_start)
        if idx == -1:
            return ""
        start = idx + len(field_start)
        end = len(text)
        for marker in end_fields:
            pos = text.find(marker + ":", start)
            if pos != -1 and pos < end:
                end = pos
        return text[start:end].strip()

    def _extract_all_fields(self, text: str, field_names: List[str]) -> Dict[str, str]:
        result = {}
        for i, fn in enumerate(field_names):
            next_fn = field_names[i + 1] if i + 1 < len(field_names) else "___END___"
            pat = re.escape(fn) + r":\s*(.*?)(?=\s*" + re.escape(next_fn) + r":|\s*$)"
            m = re.search(pat, text, re.DOTALL)
            result[fn] = m.group(1).strip() if m else ""
        return result

    def _build_name(self, name_str: str) -> str:
        if not name_str:
            return ""
        parts = {"1": "", "2": "", "3": "", "4": ""}
        for key in ["1", "2", "3", "4"]:
            next_keys = [k for k in ["1", "2", "3", "4"] if k > key]
            if next_keys:
                pat = re.escape(key) + r":\s*(.+?)\s*(?=" + "|".join(
                    re.escape(k) + ":" for k in next_keys) + r")"
            else:
                pat = re.escape(key) + r":\s*(.+)"

            m = re.search(pat, name_str)
            if m:
                val = m.group(1).strip()
                if val and val.lower() != "na":
                    parts[key] = val
        # 构建: FIRST MIDDLE LAST SUFFIX
        name_parts = []
        for k in ["2", "3", "1", "4"]:
            if parts[k]:
                name_parts.append(parts[k])
        return " ".join(name_parts) if name_parts else name_str.strip()

    def _clean_val(self, value: str) -> str:
        if not value:
            return ""
        value = re.sub(r'\s+', ' ', value).strip()
        return "" if value.lower() == "na" else value

    def _guess_country(self, nationality: str) -> str:
        return guess_country_from_text(nationality)

    def _parse_date_str(self, date_str: str) -> Optional[Any]:
        if not date_str or date_str == "na":
            return None
        # "10 Dec 1948" 格式
        m = re.search(
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})',
            date_str, re.IGNORECASE
        )
        if m:
            months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                      "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
            mo = months.get(m.group(2).lower())
            if mo:
                try:
                    return date(int(m.group(3)), mo, int(m.group(1)))
                except ValueError:
                    pass
        # YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        # 仅年份
        m = re.search(r'^(\d{4})$', date_str.strip())
        if m:
            try:
                return date(int(m.group(1)), 1, 1)
            except ValueError:
                pass
        return None

    def _print_un_summary(self, records: List[SanctionList]):
        by_committee: Dict[str, int] = {}
        by_type: Dict[str, int] = {"INDIVIDUAL": 0, "ORGANIZATION": 0}
        for r in records:
            ref = r.reference_id or ""
            prefix = ref[:ref.rindex('.')] if '.' in ref else "??"
            by_committee[prefix] = by_committee.get(prefix, 0) + 1
            by_type[r.entity_type] = by_type.get(r.entity_type, 0) + 1

        self.stdout.write("\n  按委员会分组:")
        for k, v in sorted(by_committee.items(), key=lambda x: -x[1]):
            info = COMMITTEE_MAP.get(k, {"program": k})
            self.stdout.write(f"    {k} ({info['program']}): {v} 条")
        self.stdout.write(f"\n  按类型: 个人={by_type.get('INDIVIDUAL', 0)}, "
                          f"实体={by_type.get('ORGANIZATION', 0)}")

    # ═════════════════════════════════════════════════════════
    #  OFAC Enhanced XML 导入 (流式解析)
    # ═════════════════════════════════════════════════════════
    def _import_ofac(self, file_path: str, dry_run: bool, max_entries: int):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'━' * 60}\n  OFAC Enhanced XML 导入\n  文件: {file_path}\n{'━' * 60}"
        ))

        xml_path = self._prepare_xml(file_path)
        if not xml_path:
            return

        self.stdout.write(f"  XML 文件: {xml_path}")
        file_size = os.path.getsize(xml_path)
        self.stdout.write(f"  文件大小: {file_size:,} 字节 ({file_size / 1024 / 1024:.1f} MB)")

        # 流式解析
        self.stdout.write("\n  流式解析中...")
        records: List[SanctionList] = []
        batch: List[SanctionList] = []
        count = 0
        batch_num = 0

        context = ET.iterparse(xml_path, events=("start", "end"))
        context = iter(context)
        event, root = next(context)  # root = sanctionsData

        # 默认命名空间
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        ent_tag = f"{ns}entity"
        ent_end = f"end"

        for event, elem in context:
            if event == "end" and elem.tag == ent_tag:
                rec = self._parse_ofac_entity(elem, ns)
                if rec:
                    if dry_run:
                        records.append(rec)
                        count += 1
                    else:
                        batch.append(rec)
                        count += 1
                        if len(batch) >= 1000:
                            batch_num += 1
                            SanctionList.objects.bulk_create(
                                batch, batch_size=500, ignore_conflicts=True
                            )
                            self.stdout.write(
                                f"    已写入 {count:,} 条 (批次 {batch_num})"
                            )
                            batch = []

                    if max_entries and count >= max_entries:
                        break

                # 清理元素释放内存
                elem.clear()

        # 写入剩余批次
        if not dry_run and batch:
            batch_num += 1
            SanctionList.objects.bulk_create(
                batch, batch_size=500, ignore_conflicts=True
            )
            self.stdout.write(f"    已写入 {count:,} 条 (批次 {batch_num})")

        self.stdout.write(self.style.SUCCESS(
            f"\n  OFAC 解析完成: 共 {count:,} 条"
        ))

        if dry_run and records:
            self._print_ofac_summary(records)

    def _prepare_xml(self, file_path: str) -> Optional[str]:
        """如果是 zip 则解压，返回 XML 文件路径"""
        if file_path.lower().endswith(".zip"):
            self.stdout.write("  解压 ZIP 文件...")
            tmp_dir = tempfile.mkdtemp(prefix="ofac_")
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(tmp_dir)
            # 找 XML 文件
            for fn in os.listdir(tmp_dir):
                if fn.lower().endswith(".xml"):
                    return os.path.join(tmp_dir, fn)
            self.stderr.write(self.style.ERROR("ZIP 中未找到 XML 文件"))
            return None
        return file_path

    def _parse_ofac_entity(self, elem, ns: str) -> Optional[SanctionList]:
        """解析单个 <entity> 元素"""
        # ── 实体类型 ──
        entity_type_raw = ""
        general_info = elem.find(f"{ns}generalInfo")
        if general_info is not None:
            et = general_info.find(f"{ns}entityType")
            if et is not None:
                entity_type_raw = et.text or ""
        entity_type = OFAC_TYPE_MAP.get(entity_type_raw, "ENTITY")

        # ── 制裁项目 ──
        programs = []
        prog_container = elem.find(f"{ns}sanctionsPrograms")
        if prog_container is not None:
            for sp in prog_container.findall(f"{ns}sanctionsProgram"):
                if sp.text:
                    programs.append(sp.text.strip())

        # ── 发布日期 ──
        effective_date = None
        sl_container = elem.find(f"{ns}sanctionsLists")
        if sl_container is not None:
            sl = sl_container.find(f"{ns}sanctionsList")
            if sl is not None:
                dp = sl.get("datePublished", "")
                if dp:
                    try:
                        effective_date = datetime.strptime(dp[:10], "%Y-%m-%d").date()
                    except ValueError:
                        pass

        # ── 名称 + 别名 ──
        primary_name = ""
        aliases: List[str] = []
        title = ""
        names_container = elem.find(f"{ns}names")
        if names_container is not None:
            for name_elem in names_container.findall(f"{ns}name"):
                is_primary = name_elem.findtext(f"{ns}isPrimary", "false").strip() == "true"
                translations = name_elem.find(f"{ns}translations")
                if translations is None:
                    continue
                translation = translations.find(f"{ns}translation")
                if translation is None:
                    continue
                full_name = translation.findtext(f"{ns}formattedFullName", "").strip()
                if not full_name:
                    # 拼接 first + last
                    first = translation.findtext(f"{ns}formattedFirstName", "").strip()
                    last = translation.findtext(f"{ns}formattedLastName", "").strip()
                    full_name = " ".join(p for p in [first, last] if p).strip()

                if is_primary:
                    primary_name = full_name
                    # title (仅个人)
                    if entity_type == "INDIVIDUAL":
                        title = general_info.findtext(f"{ns}title", "").strip() if general_info else ""
                elif full_name:
                    aliases.append(full_name)

        if not primary_name and not aliases:
            return None
        entity_name = primary_name or aliases[0]

        # ── 地址 ──
        country = ""
        address_parts: List[str] = []
        addr_container = elem.find(f"{ns}addresses")
        if addr_container is not None:
            for addr_elem in addr_container.findall(f"{ns}address"):
                if not country:
                    country = addr_elem.findtext(f"{ns}country", "").strip()
                translations = addr_elem.find(f"{ns}translations")
                if translations is not None:
                    tr = translations.find(f"{ns}translation")
                    if tr is not None:
                        for ap in tr.findall(f"{ns}addressParts"):
                            for part in ap.findall(f"{ns}addressPart"):
                                ptype = part.findtext(f"{ns}type", "").strip()
                                pval = part.findtext(f"{ns}value", "").strip()
                                if pval:
                                    address_parts.append(pval)
        address = ", ".join(address_parts)[:1000] if address_parts else ""

        # ── Features (出生日期等) ──
        dob = ""
        nationality = ""
        id_number = ""
        feat_container = elem.find(f"{ns}features")
        if feat_container is not None:
            for feat in feat_container.findall(f"{ns}feature"):
                ftype = feat.findtext(f"{ns}type", "").strip()
                fval = feat.findtext(f"{ns}value", "").strip()
                ftype_lower = ftype.lower()
                if "birthdate" in ftype_lower and not dob:
                    dob = fval[:64]
                elif "nationality" in ftype_lower or "citizenship" in ftype_lower:
                    if not nationality:
                        nationality = fval[:64]
                elif "passport" in ftype_lower or "id" in ftype_lower or "identification" in ftype_lower:
                    if not id_number:
                        id_number = fval[:256]

        # ── 风险等级 ──
        high_prog = {"SDGT", "IRAN", "NKOREA", "CUBA", "SYRIA", "SDNTK", "RUSSIA-EO14024"}
        risk = "HIGH" if any(p in high_prog for p in programs) else "MEDIUM"

        # ── 制裁原因 ──
        reason = "; ".join(programs) if programs else "SDN"
        if title:
            reason = f"Title: {title}; {reason}"

        return SanctionList(
            list_type="OFAC",
            entity_type=entity_type,
            entity_name=entity_name[:256],
            alias_names=", ".join(aliases)[:500],
            reference_id="",
            risk_level=risk,
            id_number=id_number,
            nationality=nationality,
            date_of_birth=dob,
            place_of_birth="",
            address=address,
            country=normalize_country_display(country),
            sanction_reason=reason[:500],
            effective_date=effective_date,
            review_date=self._calc_review_date(risk),
            is_active=True,
        )

    def _print_ofac_summary(self, records: List[SanctionList]):
        by_type: Dict[str, int] = {}
        by_prog: Dict[str, int] = {}
        by_country: Dict[str, int] = {}
        for r in records:
            by_type[r.entity_type] = by_type.get(r.entity_type, 0) + 1
            if r.country:
                by_country[r.country] = by_country.get(r.country, 0) + 1
            for p in r.sanction_reason.split(";"):
                p = p.strip()
                if p and not p.startswith("Title:"):
                    by_prog[p] = by_prog.get(p, 0) + 1

        self.stdout.write("\n  按类型分布:")
        type_map = {
            "INDIVIDUAL": "Individual",
            "ENTITY": "Entity",
            "ORGANIZATION": "Organization",
            "COUNTRY": "Country",
            "REGION": "Region",
        }
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            self.stdout.write(f"    {type_map.get(t, t)}: {c:,}")
        self.stdout.write("\n  按制裁项目 (Top 10):")
        for p, c in sorted(by_prog.items(), key=lambda x: -x[1])[:10]:
            self.stdout.write(f"    {p}: {c:,}")
        self.stdout.write("\n  按国家 (Top 10):")
        for c, n in sorted(by_country.items(), key=lambda x: -x[1])[:10]:
            self.stdout.write(f"    {c}: {n:,}")

    # ═════════════════════════════════════════════════════════
    #  汇总统计
    # ═════════════════════════════════════════════════════════
    def _print_stats(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'━' * 60}\n  导入结果汇总\n{'━' * 60}"
        ))
        for lt, label in [("UN", "联合国"), ("OFAC", "美国OFAC")]:
            count = SanctionList.objects.filter(list_type=lt, is_active=True).count()
            if count:
                high = SanctionList.objects.filter(
                    list_type=lt, risk_level="HIGH", is_active=True
                ).count()
                self.stdout.write(f"  {label:8s}: {count:>6,} 条 (高风险 {high:,})")
        total = SanctionList.objects.count()
        self.stdout.write(self.style.SUCCESS(f"\n  总计: {total:,} 条制裁名单"))
