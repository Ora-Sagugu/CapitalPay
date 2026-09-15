"""导入制裁名单命令 — OFAC / UN

用法:
    python manage.py import_sanctions --from-official --reset
    python manage.py import_sanctions --from-official --limit 30 --dry-run
    python manage.py import_sanctions --use-sample --reset
"""
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.compliance.models import SanctionList


def get_data():
    """返回 42 条制裁名单样本数据"""
    return [
        # ========================================
        #  OFAC 制裁名单（美国财政部外国资产控制办公室）
        # ========================================
        # --- OFAC - 企业 ---
        {
            "entity_name": "华为技术有限公司",
            "alias_names": "Huawei Technologies Co., Ltd., 华为",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "914403001000001234",
            "country": "中国",
            "sanction_reason": "涉嫌违反美国出口管制条例，与伊朗有未经授权的技术交易",
            "effective_date": date(2019, 5, 16),
        },
        {
            "entity_name": "芯源微电子有限公司",
            "alias_names": "Xinyuan Microelectronics Co.",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "913102300000005678",
            "country": "中国",
            "sanction_reason": "向受制裁实体提供先进半导体制造设备及技术支持",
            "effective_date": date(2022, 10, 7),
        },
        {
            "entity_name": "中科曙光信息产业股份有限公司",
            "alias_names": "Sugon Information Industry Co., Ltd.",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "911100000000009012",
            "country": "中国",
            "sanction_reason": "涉及中国军方超级计算机项目，被列入实体清单",
            "effective_date": date(2019, 6, 21),
        },
        {
            "entity_name": "National Iranian Oil Company",
            "alias_names": "NIOC, 伊朗国家石油公司",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "伊朗",
            "sanction_reason": "伊朗政府控制实体，涉及大规模杀伤性武器扩散及恐怖主义支持",
            "effective_date": date(2018, 11, 5),
        },
        {
            "entity_name": "Korea Daesong Bank",
            "alias_names": "朝鲜大成银行",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "朝鲜",
            "sanction_reason": "为朝鲜大规模杀伤性武器项目提供金融服务",
            "effective_date": date(2018, 3, 22),
        },
        {
            "entity_name": "Rosneft Trading SA",
            "alias_names": "俄罗斯石油贸易公司",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "MEDIUM",
            "id_number": "",
            "country": "俄罗斯",
            "sanction_reason": "涉及委内瑞拉石油贸易，规避美国制裁",
            "effective_date": date(2020, 2, 18),
        },
        {
            "entity_name": "Cosco Shipping Tanker (Dalian) Co., Ltd.",
            "alias_names": "中远海运油轮（大连）有限公司",
            "entity_type": "ORGANIZATION",
            "list_type": "OFAC",
            "risk_level": "MEDIUM",
            "id_number": "",
            "country": "中国",
            "sanction_reason": "涉嫌运输伊朗石油产品",
            "effective_date": date(2019, 9, 25),
        },
        # --- OFAC - 个人 ---
        {
            "entity_name": "MA, Xiaohong",
            "alias_names": "马晓红, MA Xiao Hong",
            "entity_type": "INDIVIDUAL",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "G12345678",
            "country": "中国",
            "sanction_reason": "SDN名单，涉及向朝鲜转让大规模杀伤性武器相关技术",
            "effective_date": date(2020, 12, 8),
        },
        {
            "entity_name": "LI, Wei",
            "alias_names": "李伟, LI Wei, David Li",
            "entity_type": "INDIVIDUAL",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "EC9876543",
            "country": "中国",
            "sanction_reason": "SDN名单，涉及为伊朗伊斯兰革命卫队采购敏感物资",
            "effective_date": date(2021, 3, 15),
        },
        {
            "entity_name": "Esmaeil Qaani",
            "alias_names": "伊斯梅尔·卡尼, Qaani Esmail",
            "entity_type": "INDIVIDUAL",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "IRN1987000001",
            "country": "伊朗",
            "sanction_reason": "伊朗伊斯兰革命卫队圣城旅指挥官，支持恐怖主义活动",
            "effective_date": date(2020, 1, 10),
        },
        # --- OFAC - 船只 ---
        {
            "entity_name": "GRACE 1",
            "alias_names": "Adrian Darya 1",
            "entity_type": "ENTITY",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "IMO 9116412",
            "country": "伊朗",
            "sanction_reason": "涉嫌运输伊朗原油至叙利亚，违反制裁规定",
            "effective_date": date(2019, 7, 4),
        },
        {
            "entity_name": "MT ABYAN",
            "alias_names": "阿比扬号",
            "entity_type": "ENTITY",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "IMO 9187650",
            "country": "伊朗",
            "sanction_reason": "涉及伊朗石油走私，为伊斯兰革命卫队提供运输服务",
            "effective_date": date(2022, 6, 16),
        },
        # --- OFAC - 其他 ---
        {
            "entity_name": "Lazarus Group",
            "alias_names": "Hidden Cobra, 拉撒路组织, TEMP.Hermit",
            "entity_type": "ENTITY",
            "list_type": "OFAC",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "朝鲜",
            "sanction_reason": "朝鲜政府支持的网络攻击组织，涉及多起加密货币盗窃和金融系统攻击",
            "effective_date": date(2019, 9, 13),
        },

        # ========================================
        #  UN 联合国制裁名单（联合国安理会）
        # ========================================
        # --- UN - 企业 ---
        {
            "entity_name": "Korea Mining Development Trading Corporation",
            "alias_names": "KOMID, 朝鲜矿业发展贸易公司",
            "entity_type": "ORGANIZATION",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "朝鲜",
            "sanction_reason": "涉及弹道导弹及大规模杀伤性武器相关物资采购",
            "effective_date": date(2009, 4, 24),
        },
        {
            "entity_name": "Foreign Trade Bank of DPRK",
            "alias_names": "FTB, 朝鲜对外贸易银行",
            "entity_type": "ORGANIZATION",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "朝鲜",
            "sanction_reason": "为朝鲜核导项目提供金融服务，规避联合国制裁",
            "effective_date": date(2017, 8, 5),
        },
        {
            "entity_name": "Sharif University of Technology",
            "alias_names": "沙里夫理工大学, SUT",
            "entity_type": "ENTITY",
            "list_type": "UN",
            "risk_level": "MEDIUM",
            "id_number": "",
            "country": "伊朗",
            "sanction_reason": "与伊朗弹道导弹项目有关的科研机构",
            "effective_date": date(2016, 1, 16),
        },
        # --- UN - 个人 ---
        {
            "entity_name": "RI, Hong Sop",
            "alias_names": "李洪燮, RI Hong-sop",
            "entity_type": "INDIVIDUAL",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "DPRK1970000001",
            "country": "朝鲜",
            "sanction_reason": "朝鲜军需工业部前部长，直接参与核武器研发项目",
            "effective_date": date(2017, 6, 2),
        },
        {
            "entity_name": "PAK, Chun Il",
            "alias_names": "朴春一, PAK Chun-il",
            "entity_type": "INDIVIDUAL",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "DPRK1975000002",
            "country": "朝鲜",
            "sanction_reason": "朝鲜驻外外交官，涉嫌为核导项目采购两用物资",
            "effective_date": date(2018, 3, 30),
        },
        {
            "entity_name": "Ibrahim Jadhran",
            "alias_names": "易卜拉欣·贾德兰",
            "entity_type": "INDIVIDUAL",
            "list_type": "UN",
            "risk_level": "MEDIUM",
            "id_number": "",
            "country": "利比亚",
            "sanction_reason": "利比亚石油设施卫队前领导人，非法出口利比亚原油",
            "effective_date": date(2018, 11, 19),
        },
        # UN - 船只
        {
            "entity_name": "JIE SHUN",
            "alias_names": "捷顺号",
            "entity_type": "ENTITY",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "IMO 8512345",
            "country": "朝鲜",
            "sanction_reason": "涉嫌船对船转运朝鲜禁运物资",
            "effective_date": date(2018, 3, 30),
        },
    ]


class Command(BaseCommand):
    help = "导入 OFAC / UN 制裁名单（官方源限量 或 离线样本）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-official",
            action="store_true",
            help="从 OFAC SDN 与联合国官方 XML 各下载少量真实记录",
        )
        parser.add_argument(
            "--use-sample",
            action="store_true",
            help="使用内置硬编码样本（离线回退，默认行为）",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=30,
            metavar="N",
            help="每个名单来源最多导入条数（仅 --from-official，默认 30）",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="先清空现有制裁名单及命中明细再导入（不影响商户/订单）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只下载/解析，不写入数据库",
        )

    def handle(self, *args, **options):
        if options["from_official"]:
            self._import_official(options)
            return
        self._import_sample(options)

    def _clear_sanction_tables(self):
        from apps.compliance.models import SanctionHitDetail

        hit_deleted, _ = SanctionHitDetail.objects.all().delete()
        deleted, _ = SanctionList.objects.all().delete()
        self.stdout.write(
            f"已清空命中明细 {hit_deleted} 条, 制裁名单 {deleted} 条"
        )

    def _safe_text(self, text) -> str:
        raw = "" if text is None else str(text)
        encoding = getattr(self.stdout, "encoding", None) or "utf-8"
        return raw.encode(encoding, errors="replace").decode(encoding, errors="replace")

    def _print_totals(self):
        total = SanctionList.objects.count()
        active = SanctionList.objects.filter(is_active=True).count()
        high_risk = SanctionList.objects.filter(risk_level="HIGH", is_active=True).count()
        ofac = SanctionList.objects.filter(list_type="OFAC").count()
        un = SanctionList.objects.filter(list_type="UN").count()
        self.stdout.write(
            f"  总计: {total} 条 | 有效: {active} 条 | 高风险: {high_risk} 条"
        )
        self.stdout.write(f"  OFAC: {ofac} 条 | UN: {un} 条")

    def _import_sample(self, options):
        if options["reset"] and not options["dry_run"]:
            self._clear_sanction_tables()

        data = get_data()
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("预览模式 — 不写入数据库"))
            self.stdout.write(f"样本条数: {len(data)}")
            return

        created = 0
        skipped = 0
        for item in data:
            entity_name = item["entity_name"]
            list_type = item["list_type"]
            if SanctionList.objects.filter(
                entity_name=entity_name, list_type=list_type
            ).exists():
                skipped += 1
                continue
            SanctionList.objects.create(**item)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"制裁名单导入完成: 新增 {created} 条, 跳过(已存在) {skipped} 条"
            )
        )
        self._print_totals()

    def _import_official(self, options):
        from apps.compliance.management.commands.import_ofac_sdn import (
            download_sdn_csv,
            decode_sdn_bytes,
            parse_sdn_csv_text,
        )
        from apps.compliance.management.commands.import_un_sanctions import (
            download_un_xml,
            parse_un_xml,
            write_un_records,
        )

        limit = options["limit"] or 30
        dry_run = options["dry_run"]
        ofac_entries = []
        un_records = []

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n从官方源导入测试数据（每源最多 {limit} 条）"
        ))

        try:
            self.stdout.write("下载 OFAC SDN.CSV ...")
            csv_data = download_sdn_csv()
            ofac_entries = parse_sdn_csv_text(decode_sdn_bytes(csv_data), limit)
            self.stdout.write(self.style.SUCCESS(
                f"  OFAC 解析完成: {len(ofac_entries)} 条"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"  OFAC 下载/解析失败: {exc}"))

        try:
            self.stdout.write("下载联合国 consolidated.xml ...")
            xml_bytes = download_un_xml()
            un_records = parse_un_xml(xml_bytes, max_entries=limit)
            self.stdout.write(self.style.SUCCESS(
                f"  UN 解析完成: {len(un_records)} 条"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"  UN 下载/解析失败: {exc}"))

        if not ofac_entries and not un_records:
            raise CommandError(
                "官方源均不可用。可用 python manage.py import_sanctions --use-sample 导入离线样本。"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n预览模式 — 不写入数据库"))
            for entry in ofac_entries[:5]:
                self.stdout.write(
                    f"  [OFAC/{entry.entity_type}] "
                    f"{self._safe_text(entry.entity_name)} "
                    f"({self._safe_text(entry.country)})"
                )
            for rec in un_records[:5]:
                self.stdout.write(
                    f"  [UN/{rec['entity_type']}] "
                    f"{self._safe_text(rec['entity_name'])} "
                    f"({self._safe_text(rec.get('country', ''))})"
                )
            return

        if options["reset"]:
            self._clear_sanction_tables()

        if ofac_entries:
            created = SanctionList.objects.bulk_create(
                ofac_entries, ignore_conflicts=True, batch_size=200
            )
            self.stdout.write(f"  写入 OFAC: {len(created)} 条")

        if un_records:
            created, skipped = write_un_records(un_records)
            self.stdout.write(f"  写入 UN: 新增 {created} 条, 跳过 {skipped} 条")

        self.stdout.write(self.style.SUCCESS("\n官方制裁名单导入完成"))
        self._print_totals()
