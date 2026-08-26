"""
管理命令：导入联合国安理会综合制裁名单 (consolidatedLegacyByNAME.html)

用法：
    # 从默认路径导入
    python manage.py import_un_sanctions --reset

    # 从指定文件导入
    python manage.py import_un_sanctions --file path/to/consolidatedLegacyByNAME.html --reset

    # 试运行（不写入数据库）
    python manage.py import_un_sanctions --file path/to/file.html --dry-run

数据来源：联合国安全理事会综合名单
"""

import re
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from django.core.management.base import BaseCommand
from bs4 import BeautifulSoup

from apps.compliance.models import SanctionList


# ── 委员会/制裁项目映射 ─────────────────────────────────────
COMMITTEE_MAP: Dict[str, Dict[str, str]] = {
    "QDi": {"program": "Al-Qaida/ISIL (1267/1989/2253)", "country": "多国"},
    "TAi": {"program": "Taliban (1988)", "country": "阿富汗"},
    "KPi": {"program": "朝鲜 (1718)", "country": "朝鲜"},
    "IQi": {"program": "伊拉克 (1518)", "country": "伊拉克"},
    "CDi": {"program": "刚果民主共和国 (1533)", "country": "刚果民主共和国"},
    "IRi": {"program": "伊朗 (1737)", "country": "伊朗"},
    "LYi": {"program": "利比亚 (1970)", "country": "利比亚"},
    "SOi": {"program": "索马里 (751)", "country": "索马里"},
    "CFi": {"program": "中非共和国 (2127)", "country": "中非共和国"},
    "SDi": {"program": "苏丹 (1591)", "country": "苏丹"},
    "HTi": {"program": "海地 (2653)", "country": "海地"},
    "YEi": {"program": "也门 (2140)", "country": "也门"},
    "GBi": {"program": "几内亚比绍 (2048)", "country": "几内亚比绍"},
    "SSi": {"program": "南苏丹 (2206)", "country": "南苏丹"},
    "QDe": {"program": "Al-Qaida/ISIL (1267/1989/2253)", "country": "多国"},
    "TAe": {"program": "Taliban (1988)", "country": "阿富汗"},
    "KPe": {"program": "朝鲜 (1718)", "country": "朝鲜"},
    "IQe": {"program": "伊拉克 (1518)", "country": "伊拉克"},
    "CDe": {"program": "刚果民主共和国 (1533)", "country": "刚果民主共和国"},
    "IRe": {"program": "伊朗 (1737)", "country": "伊朗"},
    "LYe": {"program": "利比亚 (1970)", "country": "利比亚"},
    "SOe": {"program": "索马里 (751)", "country": "索马里"},
    "CFe": {"program": "中非共和国 (2127)", "country": "中非共和国"},
    "HTe": {"program": "海地 (2653)", "country": "海地"},
    "YEe": {"program": "也门 (2140)", "country": "也门"},
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


class Command(BaseCommand):
    help = "导入联合国安理会综合制裁名单 (consolidatedLegacyByNAME.html)"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, default=None,
                           help="HTML文件路径 (默认: ~/Downloads/consolidatedLegacyByNAME.html)")
        parser.add_argument("--reset", action="store_true", default=False,
                           help="导入前清空所有UN数据")
        parser.add_argument("--dry-run", action="store_true", default=False,
                           help="只解析不写入数据库")

    def handle(self, *args, **options):
        file_path = options["file"]
        if not file_path:
            file_path = os.path.expanduser("~/Downloads/consolidatedLegacyByNAME.html")
        if not os.path.exists(file_path):
            self.stderr.write(f"文件不存在: {file_path}")
            return

        reset = options["reset"]
        dry_run = options["dry_run"]

        self.stdout.write(f"读取文件: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.stdout.write(f"文件大小: {len(html_content):,} 字节")

        soup = BeautifulSoup(html_content, "html.parser")

        # 提取生成日期
        for p in soup.find_all("p"):
            if "文件生成日期" in p.get_text():
                self.stdout.write(f"  {p.get_text().strip()[:80]}")
                break

        # 找到两个表格
        tables = soup.find_all("table", id="sanctions")
        if not tables:
            self.stderr.write("未找到制裁名单表格")
            return

        # 解析个人
        self.stdout.write("\n解析个人记录...")
        individual_records = self._parse_table(tables[0], "PERSON")
        self.stdout.write(f"  个人: {len(individual_records)} 条")

        # 解析实体
        self.stdout.write("\n解析实体记录...")
        entity_records = []
        if len(tables) > 1:
            entity_records = self._parse_table(tables[1], "COMPANY")
            self.stdout.write(f"  实体: {len(entity_records)} 条")

        all_records = individual_records + entity_records
        self.stdout.write(f"\n总计: {len(all_records)} 条制裁记录")

        # 验证名称覆盖率
        empty_names = sum(1 for r in all_records if not r["entity_name"])
        if empty_names:
            self.stderr.write(f"警告: {empty_names} 条记录名称为空")

        if dry_run:
            self._print_summary(all_records)
            return

        # 写入数据库
        self.stdout.write("\n写入数据库...")
        if reset:
            deleted, _ = SanctionList.objects.filter(list_type="UN").delete()
            self.stdout.write(f"  已清除 {deleted} 条旧 UN 数据")

        created = 0
        skipped = 0
        for rec in all_records:
            try:
                # 转换日期
                eff_date = None
                if rec.get("listed_date") and re.match(r'\d{4}-\d{2}-\d{2}', str(rec["listed_date"])):
                    try:
                        eff_date = datetime.strptime(rec["listed_date"], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                SanctionList.objects.create(
                    list_type="UN",
                    entity_type=rec["entity_type"],
                    entity_name=rec["entity_name"],
                    reference_id=rec["reference_id"],
                    alias_names=rec.get("aliases", ""),
                    country=rec.get("country", ""),
                    nationality=rec.get("nationality", ""),
                    date_of_birth=rec.get("date_of_birth") or "",
                    place_of_birth=rec.get("place_of_birth", ""),
                    id_number=rec.get("id_number", ""),
                    address=rec.get("address", ""),
                    sanction_reason=rec.get("sanction_reason", ""),
                    risk_level=rec.get("risk_level", "HIGH"),
                    effective_date=eff_date,
                    is_active=True,
                )
                created += 1
            except Exception as e:
                self.stderr.write(f"  跳过 {rec['reference_id']}: {e}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"  导入完成: 新增 {created} 条, 跳过 {skipped} 条")
        )
        self._print_summary(all_records)

    # ── 核心解析方法 ─────────────────────────────────────────

    def _parse_table(self, table, entity_type: str) -> List[Dict[str, Any]]:
        records = []
        rows = table.find_all("tr", class_="rowtext")
        for row in rows:
            td = row.find("td")
            if not td:
                continue
            text = td.get_text(" ", strip=True)
            rec = self._parse_individual(text) if entity_type == "PERSON" else self._parse_entity(text)
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
            "entity_type": "PERSON",
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
            "entity_type": "COMPANY",
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
        keywords = {
            "阿富汗": "阿富汗", "朝鲜": "朝鲜", "伊拉克": "伊拉克",
            "刚果": "刚果民主共和国", "伊朗": "伊朗", "利比亚": "利比亚",
            "索马里": "索马里", "中非": "中非共和国", "苏丹": "苏丹",
            "海地": "海地", "也门": "也门", "几内亚比绍": "几内亚比绍",
            "南苏丹": "南苏丹", "俄罗斯": "俄罗斯联邦",
            "叙利亚": "阿拉伯叙利亚共和国",
            "阿尔及利亚": "阿尔及利亚", "巴基斯坦": "巴基斯坦",
            "沙特": "沙特阿拉伯", "尼日利亚": "尼日利亚", "马里": "马里",
            "法国": "法国", "英国": "英国", "德国": "德国",
            "意大利": "意大利", "哥伦比亚": "哥伦比亚",
            "阿拉伯联合酋长国": "阿拉伯联合酋长国",
            "中国": "中国", "日本": "日本", "黎巴嫩": "黎巴嫩",
            "埃及": "埃及", "摩洛哥": "摩洛哥", "突尼斯": "突尼斯",
            "卡塔尔": "卡塔尔", "科威特": "科威特",
            "土耳其": "土耳其", "印度": "印度",
            "印度尼西亚": "印度尼西亚", "马来西亚": "马来西亚",
            "菲律宾": "菲律宾", "泰国": "泰国",
            "肯尼亚": "肯尼亚", "南非": "南非",
            "比利时": "比利时", "荷兰": "荷兰", "瑞士": "瑞士",
            "奥地利": "奥地利", "瑞典": "瑞典",
            "西班牙": "西班牙", "希腊": "希腊",
            "乌克兰": "乌克兰", "白俄罗斯": "白俄罗斯",
            "澳大利亚": "澳大利亚", "加拿大": "加拿大",
            "阿拉伯": "阿拉伯联合酋长国",
        }
        for kw, cn in keywords.items():
            if kw in (nationality or ""):
                return cn
        return ""

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
        by_type: Dict[str, int] = {"PERSON": 0, "COMPANY": 0}
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
        self.stdout.write(f"\n按类型: 个人={by_type.get('PERSON',0)}, 实体={by_type.get('COMPANY',0)}")
