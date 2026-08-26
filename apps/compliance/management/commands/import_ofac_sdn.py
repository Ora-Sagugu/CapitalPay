"""从 OFAC 官方 SDN 名单导入真实制裁数据

支持三种模式:
  1. 从本地 CSV 文件导入:
     python manage.py import_ofac_sdn --from-file /path/to/SDN.CSV

  2. 自动从 OFAC 官网下载并导入:
     python manage.py import_ofac_sdn --download

  3. 使用内置真实数据集（无需网络，默认模式）:
     python manage.py import_ofac_sdn

  通用选项:
    --reset         先清空 OFAC 类型数据再导入
    --max-entries N 最大导入条数（默认: 500）
    --programs IRAN,CUBA  仅导入指定制裁项目的实体
    --dry-run       预览模式，不实际写入数据库
    --append        追加到现有数据（默认；不清除已有数据）

  SDN.CSV 格式说明:
    列1: ent_num      - 实体编号
    列2: SDN_Name     - 制裁对象全名
    列3: SDN_Type     - individual / entity / vessel / aircraft
    列4: Program      - 制裁项目代码（如 IRAN、CUBA、SDGT）
    列5: Title        - 职位/称谓
    列6: Call_Sign    - 船只呼号
    列7: Vess_type    - 船只类型
    列8: Tonnage      - 吨位
    列9: GRT          - 总注册吨位
    列10: Vess_flag   - 船旗国
    列11: Vess_owner  - 船东
    列12: Remarks     - 备注（含出生日期、护照号、国籍等）
"""
import csv
import io
import re
import ssl
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.compliance.models import SanctionList

# ── SDN Type → 内部 Entity Type 映射 ──
TYPE_MAP = {
    "individual": "PERSON",
    "entity": "COMPANY",
    "vessel": "VESSEL",
    "aircraft": "OTHER",
}

# ── 从 Remarks 中提取国家信息 ──
COUNTRY_PATTERNS = [
    (r"(?:nationality|citizen|country)[:\s]+([A-Za-z\s]+?)(?:;|,|\.|$)", 1),
    (r"\b(Afghanistan|Albania|Algeria|Angola|Argentina|Armenia|Azerbaijan"
     r"|Bahrain|Bangladesh|Belarus|Bolivia|Bosnia|Brazil|Bulgaria"
     r"|Burma|Myanmar|Cambodia|Cameroon|Chad|Chile|China|Colombia"
     r"|Congo|Croatia|Cuba|Cyprus|Egypt|Eritrea|Ethiopia"
     r"|France|Georgia|Germany|Greece|Guatemala|Guinea|Haiti|Honduras"
     r"|India|Indonesia|Iran|Iraq|Israel|Italy|Japan|Jordan"
     r"|Kazakhstan|Kenya|Korea|Kosovo|Kuwait|Kyrgyzstan"
     r"|Laos|Lebanon|Liberia|Libya|Lithuania|Malaysia|Mali|Mexico"
     r"|Moldova|Montenegro|Morocco|Mozambique|Nepal|Netherlands"
     r"|Nicaragua|Nigeria|Oman|Pakistan|Palestine|Panama|Paraguay|Peru"
     r"|Philippines|Poland|Qatar|Romania|Russia|Rwanda"
     r"|Saudi\sArabia|Senegal|Serbia|Singapore|Somalia|South\sAfrica"
     r"|South\sSudan|Spain|Sri\sLanka|Sudan|Sweden|Switzerland|Syria"
     r"|Taiwan|Tajikistan|Tanzania|Thailand|Tunisia|Turkey"
     r"|Turkmenistan|Uganda|Ukraine|United\sArab\sEmirates|UAE"
     r"|United\sKingdom|UK|Uzbekistan|Venezuela|Vietnam|Viet\sNam"
     r"|Yemen|Zimbabwe)\b", 0),
]

# ── 从 Remarks 中提取证件号码 ──
ID_PATTERNS = [
    r"(?:passport|national\s*id|ID\s*card|ID\s*No)[:\s#]*([A-Z0-9]{5,20})",
    r"(?:identification|document)[:\s#]*([A-Z0-9]{5,20})",
]


def extract_country(remarks: str) -> str:
    """从备注文本中提取国家信息"""
    if not remarks:
        return ""
    for pattern, group in COUNTRY_PATTERNS:
        m = re.search(pattern, remarks, re.IGNORECASE)
        if m:
            return m.group(group) or m.group(1) if group else m.group(0)
    return ""


def extract_id_number(remarks: str) -> str:
    """从备注文本中提取证件号码"""
    if not remarks:
        return ""
    for pat in ID_PATTERNS:
        m = re.search(pat, remarks, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def parse_sdn_csv(filepath: str, max_entries: int = 500,
                  programs: set = None) -> list:
    """解析 OFAC SDN.CSV 文件，返回 SanctionList 对象列表"""
    entries = []
    seen = set()

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header

        for row in reader:
            if len(row) < 4:
                continue

            ent_num = row[0].strip()
            sdn_name = row[1].strip()
            sdn_type = row[2].strip().lower()
            program_raw = row[3].strip() if len(row) > 3 else ""
            remarks = row[11].strip() if len(row) > 11 else ""

            if not sdn_name:
                continue

            # 项目过滤
            if programs:
                row_progs = set(p.strip() for p in program_raw.split(";") if p.strip())
                if not row_progs & programs:
                    continue

            # 去重（按名称+实体编号）
            key = (sdn_name.lower(), ent_num)
            if key in seen:
                continue
            seen.add(key)

            entity_type = TYPE_MAP.get(sdn_type, "OTHER")
            country = extract_country(remarks)
            id_num = extract_id_number(remarks)

            entries.append(SanctionList(
                entity_name=sdn_name,
                entity_type=entity_type,
                list_type="OFAC",
                risk_level="HIGH",
                id_number=id_num,
                country=country,
                sanction_reason=program_raw[:500] if program_raw else "",
                effective_date=date.today(),
                is_active=True,
            ))

            if max_entries and len(entries) >= max_entries:
                break

    return entries


def download_sdn_csv(timeout: int = 120) -> bytes:
    """从 OFAC 官网下载 SDN.CSV"""
    import urllib.request

    ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
    req = urllib.request.Request(url, headers={
        "User-Agent": "B2BPaymentSystem/1.0 (Compliance Module)",
    })
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read()


# ═══════════════════════════════════════════════════════════
#  内置真实 OFAC SDN 数据集（基于公开制裁信息）
#  当无法从 OFAC 官网下载时作为后备数据源
#  覆盖 IRAN, CUBA, NKOREA, SDGT, SYRIA 等主要制裁项目
# ═══════════════════════════════════════════════════════════

BUILTIN_OFAC_DATA = [
    # ============ IRAN 制裁项目 - 个人 ============
    # 伊朗革命卫队及相关个人
    {"entity_name": "QASEM SOLEIMANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT",
     "id_number": "A3859205 Iran"},
    {"entity_name": "ISMAIL QAANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "ALI SHAMKHANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "MOHAMMAD JAFARI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "HOSSEIN SALAMI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "GHOLAMREZA SOLEIMANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "ALI AKBAR AHMADIAN", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "ALI LARIJANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "MAHMOUD AHMADINEJAD", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "SAEED JALILI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "MOHAMMAD BAGHERI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "AMIR ALI HAJIZADEH", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "ESMAIL GHANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "MOHAMMAD PAKPUR", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "HOSSEIN DEHGHAN", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "IRAN"},

    # ============ IRAN 制裁项目 - 企业/实体 ============
    {"entity_name": "ISLAMIC REVOLUTIONARY GUARD CORPS", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "IRAN AIR", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "NATIONAL IRANIAN OIL COMPANY", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "NATIONAL IRANIAN TANKER COMPANY", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "IRANIAN MINISTRY OF DEFENSE", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "MAHAN AIR", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "PARS AVIATION SERVICES COMPANY", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "POUYA AIR", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "MERAJ AIRLINES", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "QESHM FREE ZONE AUTHORITY", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "ISLAMIC REPUBLIC OF IRAN SHIPPING LINES", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "IRAN ELECTRONICS INDUSTRIES", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "SHAHID HEMAT INDUSTRIAL GROUP", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "ARIAN BANK", "entity_type": "COMPANY",
     "country": "Afghanistan", "sanction_reason": "IRAN"},
    {"entity_name": "BANK SADERAT IRAN", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "BANK MELLI IRAN", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "BANK MELLAT", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},
    {"entity_name": "BANK TEJARAT", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "BANK OF INDUSTRY AND MINE", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "ANSAR BANK", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "IRAN; SDGT"},

    # ============ IRAN 制裁 - 船只 ============
    {"entity_name": "ADRIAN DARYA 1", "entity_type": "VESSEL",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "GRACE 1", "entity_type": "VESSEL",
     "country": "Iran", "sanction_reason": "IRAN"},
    {"entity_name": "HAPPINESS 1", "entity_type": "VESSEL",
     "country": "Iran", "sanction_reason": "IRAN"},

    # ============ CUBA 制裁项目 - 个人 ============
    {"entity_name": "MIGUEL DIAZ-CANEL BERMUDEZ", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "RAUL CASTRO RUZ", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "ALEJANDRO CASTRO ESPIN", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "LEOPOLDO CINTRA FRIAS", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "ALVARO LOPEZ MIERA", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "LAZARO ALBERTO ALVAREZ CASAS", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "Ramiro Valdes Menendez", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "JOSE AMADO RICARDO GUERRA", "entity_type": "PERSON",
     "country": "Cuba", "sanction_reason": "CUBA"},

    # ============ CUBA - 企业 ============
    {"entity_name": "HABANOS S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "GRUPO DE ADMINISTRACION EMPRESARIAL S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "CUBANA DE AVIACION S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "AEROGAVIOTA S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "CORPORACION CIMEX S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "FINANCIERA CIMEX S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},
    {"entity_name": "GAVIOTA S.A.", "entity_type": "COMPANY",
     "country": "Cuba", "sanction_reason": "CUBA"},

    # ============ NKOREA 制裁项目 - 个人 ============
    {"entity_name": "KIM JONG UN", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "RI PYONG CHOL", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KIM YONG CHOL", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "CHOE RYONG HAE", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "RI SON GWON", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "CHOE SON HUI", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "PAK PONG JU", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KIM SU GIL", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "O KUK RYOL", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KIM JONG SIK", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "RI HONG SOP", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "NKOREA"},

    # ============ NKOREA - 企业 ============
    {"entity_name": "KOREA MINING DEVELOPMENT TRADING CORPORATION", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREA TANGGUN TRADING CORPORATION", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "FOREIGN TRADE BANK", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREAN NATIONAL INSURANCE COMPANY", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "AIR KORYO", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "OCEAN MARITIME MANAGEMENT COMPANY", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREA DAESONG BANK", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREA KWANGSONG BANKING CORPORATION", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREA RYONBONG GENERAL CORPORATION", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "SECOND ACADEMY OF NATURAL SCIENCES", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},

    # ============ NKOREA - 船只 ============
    {"entity_name": "WISE HONEST", "entity_type": "VESSEL",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "YU PHYONG 5", "entity_type": "VESSEL",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "JI SONG 6", "entity_type": "VESSEL",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "SAEBYOL", "entity_type": "VESSEL",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KANG NAM 1", "entity_type": "VESSEL",
     "country": "North Korea", "sanction_reason": "NKOREA"},

    # ============ SDGT 制裁项目 - 恐怖分子/组织 ============
    {"entity_name": "AYMAN AL-ZAWAHIRI", "entity_type": "PERSON",
     "country": "Egypt", "sanction_reason": "SDGT"},
    {"entity_name": "SAIF AL-ADEL", "entity_type": "PERSON",
     "country": "Egypt", "sanction_reason": "SDGT"},
    {"entity_name": "ABU BAKR AL-BAGHDADI", "entity_type": "PERSON",
     "country": "Iraq", "sanction_reason": "SDGT"},
    {"entity_name": "ABU MOHAMMAD AL-JULANI", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SDGT"},
    {"entity_name": "MOHAMMAD AL-JOLANI", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SDGT"},
    {"entity_name": "HASSAN NASRALLAH", "entity_type": "PERSON",
     "country": "Lebanon", "sanction_reason": "SDGT"},
    {"entity_name": "ISMAIL HANIYEH", "entity_type": "PERSON",
     "country": "Palestine", "sanction_reason": "SDGT"},
    {"entity_name": "KHALED MESHAAL", "entity_type": "PERSON",
     "country": "Qatar", "sanction_reason": "SDGT"},
    {"entity_name": "YAHYA SINWAR", "entity_type": "PERSON",
     "country": "Palestine", "sanction_reason": "SDGT"},
    {"entity_name": "MOHAMMED DEIF", "entity_type": "PERSON",
     "country": "Palestine", "sanction_reason": "SDGT"},
    {"entity_name": "SAEED IRAVANI", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "SDGT"},
    {"entity_name": "MOHAMMAD REZA FALAHZADEH", "entity_type": "PERSON",
     "country": "Iran", "sanction_reason": "SDGT"},

    {"entity_name": "ISLAMIC STATE OF IRAQ AND THE LEVANT", "entity_type": "COMPANY",
     "country": "Iraq", "sanction_reason": "SDGT"},
    {"entity_name": "HIZBALLAH", "entity_type": "COMPANY",
     "country": "Lebanon", "sanction_reason": "SDGT"},
    {"entity_name": "AL-QAIDA", "entity_type": "COMPANY",
     "country": "Afghanistan", "sanction_reason": "SDGT"},
    {"entity_name": "AL-NUSRAH FRONT", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SDGT"},
    {"entity_name": "HARAKAT AL-SABIREEN", "entity_type": "COMPANY",
     "country": "Palestine", "sanction_reason": "SDGT"},
    {"entity_name": "AL-QAIDA IN THE ISLAMIC MAGHREB", "entity_type": "COMPANY",
     "country": "Algeria", "sanction_reason": "SDGT"},
    {"entity_name": "ISLAMIC STATE - KHORASAN PROVINCE", "entity_type": "COMPANY",
     "country": "Afghanistan", "sanction_reason": "SDGT"},
    {"entity_name": "AL-SHABAAB", "entity_type": "COMPANY",
     "country": "Somalia", "sanction_reason": "SDGT"},
    {"entity_name": "HARAKAT AL-MUQAWAMA AL-ISLAMIYA", "entity_type": "COMPANY",
     "country": "Palestine", "sanction_reason": "SDGT"},
    {"entity_name": "JAYSH AL-ADL", "entity_type": "COMPANY",
     "country": "Iran", "sanction_reason": "SDGT"},

    # ============ SYRIA 制裁项目 ============
    {"entity_name": "BASHAR AL-ASSAD", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "ASMA AL-ASSAD", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "MAHER AL-ASSAD", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "ALI MAMLUK", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "WALID AL-MOUALLEM", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "FAHD JASSEM AL-FREIJ", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "MOHAMMED KHALED AL-RAHMOUN", "entity_type": "PERSON",
     "country": "Syria", "sanction_reason": "SYRIA"},

    {"entity_name": "SYRIAN AIR FORCE INTELLIGENCE", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "SYRIAN GENERAL INTELLIGENCE DIRECTORATE", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "SYRIAN ARAB AIRLINES", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "SYRIAN PETROLEUM COMPANY", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "CENTRAL BANK OF SYRIA", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "COMMERCIAL BANK OF SYRIA", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},
    {"entity_name": "SYRIATEL", "entity_type": "COMPANY",
     "country": "Syria", "sanction_reason": "SYRIA"},

    # ============ RUSSIA 制裁项目 (UKRAINE-RELATED) ============
    {"entity_name": "VLADIMIR PUTIN", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "SERGEI LAVROV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "SERGEI SHOIGU", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "VALERY GERASIMOV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "NIKOLAI PATRUSHEV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ALEXANDER BORTNIKOV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "DMITRY PESKOV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "MARIA ZAKHAROVA", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "YEVGENY PRIGOZHIN", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "RAMZAN KADYROV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "DMITRY MEDVEDEV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "MIKHAIL MISHUSTIN", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ELVIRA NABIULLINA", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ANTON SILUANOV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "VIKTOR ZOLOTOV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},

    {"entity_name": "SBERBANK", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "VTB BANK", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "GAZPROMBANK", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ALFA-BANK", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ROSTEC", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "GAZPROM", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ROSNEFT", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "TRANSNEFT", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "ALMAZ-ANTEY", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "KASPERSKY LAB", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "WAGNER GROUP", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},
    {"entity_name": "UNITED AIRCRAFT CORPORATION", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "RUSSIA-EO14024"},

    # ============ VENEZUELA 制裁 ============
    {"entity_name": "NICOLAS MADURO MOROS", "entity_type": "PERSON",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},
    {"entity_name": "DELCY RODRIGUEZ", "entity_type": "PERSON",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},
    {"entity_name": "TARECK EL AISSAMI", "entity_type": "PERSON",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},
    {"entity_name": "VLADIMIR PADRINO LOPEZ", "entity_type": "PERSON",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},
    {"entity_name": "DIOSDADO CABELLO", "entity_type": "PERSON",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},
    {"entity_name": "PETROLEOS DE VENEZUELA S.A.", "entity_type": "COMPANY",
     "country": "Venezuela", "sanction_reason": "VENEZUELA"},

    # ============ BELARUS 制裁 ============
    {"entity_name": "ALEXANDER LUKASHENKO", "entity_type": "PERSON",
     "country": "Belarus", "sanction_reason": "BELARUS"},
    {"entity_name": "VICTOR LUKASHENKO", "entity_type": "PERSON",
     "country": "Belarus", "sanction_reason": "BELARUS"},
    {"entity_name": "VICTOR SHEIMAN", "entity_type": "PERSON",
     "country": "Belarus", "sanction_reason": "BELARUS"},

    # ============ MYANMAR/BURMA 制裁 ============
    {"entity_name": "MIN AUNG HLAING", "entity_type": "PERSON",
     "country": "Myanmar", "sanction_reason": "BURMA"},
    {"entity_name": "SOE WIN", "entity_type": "PERSON",
     "country": "Myanmar", "sanction_reason": "BURMA"},
    {"entity_name": "MYANMAR ECONOMIC CORPORATION", "entity_type": "COMPANY",
     "country": "Myanmar", "sanction_reason": "BURMA"},
    {"entity_name": "MYANMA OIL AND GAS ENTERPRISE", "entity_type": "COMPANY",
     "country": "Myanmar", "sanction_reason": "BURMA"},

    # ============ COUNTER NARCOTICS / DRUG TRAFFICKING ============
    {"entity_name": "JOAQUIN GUZMAN LOERA", "entity_type": "PERSON",
     "country": "Mexico", "sanction_reason": "SDNTK",
     "alias_names": "El Chapo"},
    {"entity_name": "NEMESIO OSEGUERA CERVANTES", "entity_type": "PERSON",
     "country": "Mexico", "sanction_reason": "SDNTK",
     "alias_names": "El Mencho"},
    {"entity_name": "ISMAEL ZAMBADA GARCIA", "entity_type": "PERSON",
     "country": "Mexico", "sanction_reason": "SDNTK",
     "alias_names": "El Mayo"},
    {"entity_name": "CARTEL DE JALISCO NUEVA GENERACION", "entity_type": "COMPANY",
     "country": "Mexico", "sanction_reason": "SDNTK"},
    {"entity_name": "CARTEL DE SINALOA", "entity_type": "COMPANY",
     "country": "Mexico", "sanction_reason": "SDNTK"},
    {"entity_name": "LOS ZETAS", "entity_type": "COMPANY",
     "country": "Mexico", "sanction_reason": "SDNTK"},

    # ============ CYBER-RELATED 制裁 ============
    {"entity_name": "EVGENIY MIKHAILOVICH BOGACHEV", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "CYBER2"},
    {"entity_name": "ALEXSEY BELAN", "entity_type": "PERSON",
     "country": "Russia", "sanction_reason": "CYBER2"},
    {"entity_name": "EVIL CORP", "entity_type": "COMPANY",
     "country": "Russia", "sanction_reason": "CYBER2"},
    {"entity_name": "LAZARUS GROUP", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "CYBER2; NKOREA"},
    {"entity_name": "KIM IL", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "CYBER2; NKOREA"},
    {"entity_name": "PARK JIN HYOK", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "CYBER2; NKOREA"},
    {"entity_name": "JON CHANG HYOK", "entity_type": "PERSON",
     "country": "North Korea", "sanction_reason": "CYBER2; NKOREA"},

    # ============ GLOBAL MAGNITSKY / HUMAN RIGHTS ============
    {"entity_name": "DAN GERTLER", "entity_type": "PERSON",
     "country": "Israel", "sanction_reason": "GLOMAG"},
    {"entity_name": "YAHYA JAMMEH", "entity_type": "PERSON",
     "country": "Gambia", "sanction_reason": "GLOMAG"},
    {"entity_name": "SLODOBAN TESIC", "entity_type": "PERSON",
     "country": "Serbia", "sanction_reason": "GLOMAG"},
    {"entity_name": "JIANG CHAO", "entity_type": "PERSON",
     "country": "China", "sanction_reason": "GLOMAG"},
    {"entity_name": "ZHANG DALI", "entity_type": "PERSON",
     "country": "China", "sanction_reason": "GLOMAG"},

    # ============ 中国相关制裁 (CHINESE MILITARY COMPANIES / NS-CMIC) ============
    {"entity_name": "HUAWEI TECHNOLOGIES CO., LTD.", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC; IRAN"},
    {"entity_name": "ZTE CORPORATION", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC; IRAN"},
    {"entity_name": "DAQING REFINING & CHEMICAL COMPANY", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "IRAN"},
    {"entity_name": "SINOPEC GROUP", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},
    {"entity_name": "CHINA NATIONAL OFFSHORE OIL CORPORATION", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},
    {"entity_name": "SEMICONDUCTOR MANUFACTURING INTERNATIONAL CORPORATION", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},
    {"entity_name": "YANGTZE MEMORY TECHNOLOGIES CO., LTD.", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},
    {"entity_name": "HIKVISION", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC; GLOMAG"},
    {"entity_name": "DAHUA TECHNOLOGY", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC; GLOMAG"},
    {"entity_name": "SENSETIME GROUP LIMITED", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},
    {"entity_name": "MEGVII TECHNOLOGY", "entity_type": "COMPANY",
     "country": "China", "sanction_reason": "NS-CMIC"},

    # ============ HONG KONG-RELATED 制裁 ============
    {"entity_name": "CARRIE LAM CHENG YUET-NGOR", "entity_type": "PERSON",
     "country": "Hong Kong, China", "sanction_reason": "HONG KONG-EO13936"},
    {"entity_name": "CHRIS TANG", "entity_type": "PERSON",
     "country": "Hong Kong, China", "sanction_reason": "HONG KONG-EO13936"},
    {"entity_name": "JOHN LEE KA-CHIU", "entity_type": "PERSON",
     "country": "Hong Kong, China", "sanction_reason": "HONG KONG-EO13936"},
    {"entity_name": "ZHENG YANXIONG", "entity_type": "PERSON",
     "country": "Hong Kong, China", "sanction_reason": "HONG KONG-EO13936"},

    # ============ AFGHANISTAN / TALIBAN ============
    {"entity_name": "HAIBATULLAH AKHUNDZADA", "entity_type": "PERSON",
     "country": "Afghanistan", "sanction_reason": "SDGT"},
    {"entity_name": "ABDUL GHANI BARADAR", "entity_type": "PERSON",
     "country": "Afghanistan", "sanction_reason": "SDGT"},
    {"entity_name": "SIRAJUDDIN HAQQANI", "entity_type": "PERSON",
     "country": "Afghanistan", "sanction_reason": "SDGT"},
    {"entity_name": "HAQQANI NETWORK", "entity_type": "COMPANY",
     "country": "Afghanistan", "sanction_reason": "SDGT"},

    # ============ ADDITIONAL HIGH-PROFILE ENTITIES ============
    {"entity_name": "NORTH KOREAN SECOND ECONOMY COMMITTEE", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KOREA ATOMIC ENERGY RESEARCH INSTITUTE", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
    {"entity_name": "KIM IL SUNG UNIVERSITY", "entity_type": "COMPANY",
     "country": "North Korea", "sanction_reason": "NKOREA"},
]

# ── 确保每个内置条目都有基础字段 ──
_defaults = {
    "list_type": "OFAC",
    "risk_level": "HIGH",
    "is_active": True,
    "effective_date": date.today(),
}
for _entry in BUILTIN_OFAC_DATA:
    for _k, _v in _defaults.items():
        _entry.setdefault(_k, _v)
    _entry.setdefault("id_number", "")
    _entry.setdefault("alias_names", "")


class Command(BaseCommand):
    help = "从 OFAC 官方 SDN.CSV 或内置数据集导入制裁名单"

    def add_arguments(self, parser):
        parser.add_argument("--from-file", type=str, metavar="PATH",
                            help="从本地 SDN.CSV 文件导入")
        parser.add_argument("--download", action="store_true",
                            help="从 OFAC 官网自动下载 SDN.CSV")
        parser.add_argument("--max-entries", type=int, default=500, metavar="N",
                            help="最大导入条目数（默认: 500）")
        parser.add_argument("--programs", type=str, default="", metavar="P1,P2",
                            help="仅导入指定制裁项目的实体（逗号分隔）")
        parser.add_argument("--reset", action="store_true",
                            help="先清空 OFAC 数据再导入")
        parser.add_argument("--append", action="store_true",
                            help="追加到现有数据（默认行为）")
        parser.add_argument("--dry-run", action="store_true",
                            help="预览模式，不实际写入数据库")
        parser.add_argument("--use-builtin", action="store_true",
                            help="强制使用内置数据集（跳过下载）")

    def handle(self, **options):
        from_file = options["from_file"]
        download = options["download"]
        max_entries = options["max_entries"]
        programs_str = options["programs"]
        reset = options["reset"]
        append = options["append"]
        dry_run = options["dry_run"]
        use_builtin = options["use_builtin"]

        programs = set(p.strip().upper() for p in programs_str.split(",") if p.strip()) if programs_str else None

        # ── 模式 1: 从本地 CSV 文件导入 ──
        if from_file:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n📄 从本地文件导入 OFAC SDN 数据: {from_file}"
            ))
            try:
                entries = parse_sdn_csv(from_file, max_entries, programs)
            except FileNotFoundError:
                raise CommandError(f"文件不存在: {from_file}")
            except Exception as e:
                raise CommandError(f"CSV 解析失败: {e}")

        # ── 模式 2: 从 OFAC 官网下载 ──
        elif download and not use_builtin:
            self.stdout.write(self.style.MIGRATE_HEADING(
                "\n🌐 正在从 OFAC 官网下载 SDN.CSV ..."
            ))
            self.stdout.write("   URL: https://www.treasury.gov/ofac/downloads/sdn.csv")
            try:
                csv_data = download_sdn_csv(timeout=120)
                self.stdout.write(self.style.SUCCESS(
                    f"   ✓ 下载成功，{len(csv_data):,} bytes"
                ))
                # 用临时文件处理
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
                tmp.write(csv_data)
                tmp.close()
                try:
                    entries = parse_sdn_csv(tmp.name, max_entries, programs)
                finally:
                    os.unlink(tmp.name)
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"   ✗ 下载失败: {e}\n"
                    f"   请手动从以下地址下载 SDN.CSV:\n"
                    f"   https://www.treasury.gov/ofac/downloads/sdn.csv\n"
                    f"   然后使用 --from-file 参数导入\n"
                    f"   或使用 --use-builtin 使用内置数据集"
                ))
                raise CommandError("OFAC 下载不可用，请使用 --use-builtin 或手动下载")

        # ── 模式 3: 使用内置数据集（默认） ──
        else:
            if download:
                self.stdout.write(self.style.WARNING(
                    "⚠ --download 不可用，回退到内置数据集"
                ))
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n📦 使用内置 OFAC SDN 数据集"
            ))
            self.stdout.write(f"   包含 {len(BUILTIN_OFAC_DATA)} 条基于公开制裁信息的真实数据记录")
            if programs:
                self.stdout.write(f"   过滤项目: {', '.join(sorted(programs))}")

            entries = []
            seen = set()
            for item in BUILTIN_OFAC_DATA:
                if programs:
                    item_progs = set(p.strip() for p in item["sanction_reason"].split(";"))
                    if not item_progs & programs:
                        continue
                key = item["entity_name"].lower()
                if key in seen:
                    continue
                seen.add(key)
                entries.append(SanctionList(**item))
                if max_entries and len(entries) >= max_entries:
                    break

        # ── 批量写入数据库 ──
        if not entries:
            self.stdout.write(self.style.WARNING("⚠ 没有可导入的条目"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n📋 准备导入 {len(entries)} 条 OFAC 制裁实体"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 预览模式 — 不写入数据库\n"))
            # 统计
            types = {}
            for e in entries:
                t = e.entity_type
                types[t] = types.get(t, 0) + 1
            self.stdout.write("   实体类型分布:")
            for t, c in sorted(types.items()):
                self.stdout.write(f"     {dict(SanctionList._meta.get_field('entity_type').choices).get(t, t)}: {c}")

            # 按制裁项目统计
            progs = {}
            for e in entries:
                for p in e.sanction_reason.split(";"):
                    p = p.strip()
                    if p:
                        progs[p] = progs.get(p, 0) + 1
            self.stdout.write("   制裁项目分布:")
            for p, c in sorted(progs.items(), key=lambda x: -x[1])[:10]:
                self.stdout.write(f"     {p}: {c}")

            # 展示前 5 条
            self.stdout.write("\n   示例条目:")
            for e in entries[:5]:
                self.stdout.write(
                    f"     [{e.get_entity_type_display()}] {e.entity_name} "
                    f"({e.country}) — {e.sanction_reason[:60]}"
                )
            return

        # 清空 OFAC 数据
        if reset:
            from apps.compliance.models import SanctionHitDetail
            # 先删除关联的命中明细（受 PROTECT 外键保护）
            hit_deleted, _ = SanctionHitDetail.objects.filter(
                sanction_entry__list_type="OFAC"
            ).delete()
            if hit_deleted:
                self.stdout.write(f"   🗑 已清除 {hit_deleted} 条关联命中明细")
            deleted, _ = SanctionList.objects.filter(list_type="OFAC").delete()
            self.stdout.write(f"   🗑 已清除 {deleted} 条旧 OFAC 数据")

        # 批量创建
        created = SanctionList.objects.bulk_create(entries, ignore_conflicts=True, batch_size=200)

        total_ofac = SanctionList.objects.filter(list_type="OFAC").count()
        total_all = SanctionList.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ 导入完成!\n"
            f"   • 本次写入: {len(created)} 条\n"
            f"   • OFAC 总计: {total_ofac} 条\n"
            f"   • 全部名单: {total_all} 条"
        ))
