"""导入制裁名单种子数据命令 — OFAC / UN / EU / MPS / PBOC / INTERNAL

用法:
    python manage.py import_sanctions          # 追加数据
    python manage.py import_sanctions --reset  # 先清空再填充
"""
from datetime import date
from django.core.management.base import BaseCommand
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "PERSON",
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
            "entity_type": "PERSON",
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
            "entity_type": "PERSON",
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
            "entity_type": "VESSEL",
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
            "entity_type": "VESSEL",
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
            "entity_type": "OTHER",
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
            "entity_type": "COMPANY",
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
            "entity_type": "COMPANY",
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
            "entity_type": "OTHER",
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
            "entity_type": "PERSON",
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
            "entity_type": "PERSON",
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
            "entity_type": "PERSON",
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
            "entity_type": "VESSEL",
            "list_type": "UN",
            "risk_level": "HIGH",
            "id_number": "IMO 8512345",
            "country": "朝鲜",
            "sanction_reason": "涉嫌船对船转运朝鲜禁运物资",
            "effective_date": date(2018, 3, 30),
        },

        # ========================================
        #  EU 欧盟制裁名单
        # ========================================
        {
            "entity_name": "Sberbank of Russia",
            "alias_names": "俄罗斯联邦储蓄银行, Sberbank Rossii",
            "entity_type": "COMPANY",
            "list_type": "EU",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "俄罗斯",
            "sanction_reason": "俄罗斯最大国有银行，为俄罗斯政府提供关键金融服务，涉及乌克兰局势",
            "effective_date": date(2022, 7, 22),
        },
        {
            "entity_name": "Vladimir Putin",
            "alias_names": "弗拉基米尔·普京, PUTIN Vladimir Vladimirovich",
            "entity_type": "PERSON",
            "list_type": "EU",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "俄罗斯",
            "sanction_reason": "俄罗斯联邦总统，因乌克兰军事行动受欧盟制裁",
            "effective_date": date(2022, 2, 25),
        },
        {
            "entity_name": "Wagner Group",
            "alias_names": "瓦格纳集团, PMC Wagner, ChVK Vagner",
            "entity_type": "OTHER",
            "list_type": "EU",
            "risk_level": "HIGH",
            "id_number": "",
            "country": "俄罗斯",
            "sanction_reason": "俄罗斯私营军事公司，在乌克兰、叙利亚、非洲等地严重侵犯人权",
            "effective_date": date(2021, 12, 13),
        },
        {
            "entity_name": "Belarusian Republican Unitary Enterprise",
            "alias_names": "白俄罗斯钾肥公司, Belaruskali",
            "entity_type": "COMPANY",
            "list_type": "EU",
            "risk_level": "MEDIUM",
            "id_number": "",
            "country": "白俄罗斯",
            "sanction_reason": "白俄罗斯政府控制的国有企业，为卢卡申科政权提供重要财政收入",
            "effective_date": date(2021, 6, 24),
        },

        # ========================================
        #  MPS 公安部通缉/制裁名单
        # ========================================
        {
            "entity_name": "张明辉",
            "alias_names": "张明, Zhang Minghui, 老张",
            "entity_type": "PERSON",
            "list_type": "MPS",
            "risk_level": "HIGH",
            "id_number": "350102198501011234",
            "country": "中国",
            "sanction_reason": "特大跨境电信诈骗团伙主犯，涉案金额超5亿元人民币",
            "effective_date": date(2023, 1, 15),
        },
        {
            "entity_name": "深圳市鑫源投资咨询有限公司",
            "alias_names": "鑫源投资, Xinyuan Investment Consulting",
            "entity_type": "COMPANY",
            "list_type": "MPS",
            "risk_level": "HIGH",
            "id_number": "914403000000012345",
            "country": "中国",
            "sanction_reason": "涉嫌非法集资和洗钱，涉案资金超20亿元",
            "effective_date": date(2022, 9, 8),
        },
        {
            "entity_name": "林志远",
            "alias_names": "林老板, LIN Zhiyuan, Tony Lin",
            "entity_type": "PERSON",
            "list_type": "MPS",
            "risk_level": "HIGH",
            "id_number": "440303197812019876",
            "country": "中国",
            "sanction_reason": "跨境网络赌博平台运营者，涉及资金跨境转移和洗钱",
            "effective_date": date(2023, 4, 20),
        },
        {
            "entity_name": "云南瑞兴贸易有限公司",
            "alias_names": "瑞兴贸易, Ruixing Trading Co.",
            "entity_type": "COMPANY",
            "list_type": "MPS",
            "risk_level": "MEDIUM",
            "id_number": "915300000000005432",
            "country": "中国",
            "sanction_reason": "涉嫌利用边境贸易渠道进行毒品资金洗钱活动",
            "effective_date": date(2022, 11, 3),
        },

        # ========================================
        #  PBOC 中国人民银行反洗钱重点关注名单
        # ========================================
        {
            "entity_name": "广州恒达国际贸易有限公司",
            "alias_names": "恒达贸易, Hengda International Trading",
            "entity_type": "COMPANY",
            "list_type": "PBOC",
            "risk_level": "MEDIUM",
            "id_number": "914401000000009876",
            "country": "中国",
            "sanction_reason": "频繁大额跨境交易，资金来源异常，存在洗钱嫌疑",
            "effective_date": date(2022, 5, 1),
        },
        {
            "entity_name": "上海锦华进出口有限公司",
            "alias_names": "锦华进出口, Jinhua Import & Export",
            "entity_type": "COMPANY",
            "list_type": "PBOC",
            "risk_level": "MEDIUM",
            "id_number": "913100000000001122",
            "country": "中国",
            "sanction_reason": "涉及虚假贸易背景的跨境汇款，涉嫌资本外逃",
            "effective_date": date(2023, 2, 14),
        },
        {
            "entity_name": "赵建国",
            "alias_names": "老赵, ZHAO Jianguo, Jack Zhao",
            "entity_type": "PERSON",
            "list_type": "PBOC",
            "risk_level": "HIGH",
            "id_number": "110105196503012345",
            "country": "中国",
            "sanction_reason": "地下钱庄主要操作人，涉及多起跨境非法资金转移案件",
            "effective_date": date(2023, 6, 30),
        },

        # ========================================
        #  INTERNAL 内部黑名单
        # ========================================
        {
            "entity_name": "深圳市丰达电子有限公司",
            "alias_names": "丰达电子, Fengda Electronics",
            "entity_type": "COMPANY",
            "list_type": "INTERNAL",
            "risk_level": "HIGH",
            "id_number": "914403000000054321",
            "country": "中国",
            "sanction_reason": "历史交易中多次出现退单和拒付，涉嫌欺诈行为",
            "effective_date": date(2022, 3, 10),
        },
        {
            "entity_name": "陈伟强",
            "alias_names": "阿强, CHEN Weiqiang",
            "entity_type": "PERSON",
            "list_type": "INTERNAL",
            "risk_level": "HIGH",
            "id_number": "440301199002019999",
            "country": "中国",
            "sanction_reason": "多次提供虚假KYC材料，涉及多平台欺诈注册",
            "effective_date": date(2022, 7, 15),
        },
        {
            "entity_name": "北京华远科技有限公司",
            "alias_names": "华远科技, Huayuan Technology",
            "entity_type": "COMPANY",
            "list_type": "INTERNAL",
            "risk_level": "MEDIUM",
            "id_number": "911100000000009999",
            "country": "中国",
            "sanction_reason": "存在异常高频交易模式，疑似资金中转账户",
            "effective_date": date(2023, 1, 20),
        },
        {
            "entity_name": "王晓明",
            "alias_names": "小王, WANG Xiaoming",
            "entity_type": "PERSON",
            "list_type": "INTERNAL",
            "risk_level": "MEDIUM",
            "id_number": "320105198808081234",
            "country": "中国",
            "sanction_reason": "与多个高风险账户存在关联交易，疑似参与洗钱网络",
            "effective_date": date(2023, 5, 8),
        },
        {
            "entity_name": "杭州聚鑫贸易有限公司",
            "alias_names": "聚鑫贸易, Juxin Trading",
            "entity_type": "COMPANY",
            "list_type": "INTERNAL",
            "risk_level": "LOW",
            "id_number": "913301000000006666",
            "country": "中国",
            "sanction_reason": "交易模式异常，需持续监控",
            "effective_date": date(2023, 8, 12),
        },
        {
            "entity_name": "刘芳",
            "alias_names": "小芳, LIU Fang, Lisa Liu",
            "entity_type": "PERSON",
            "list_type": "INTERNAL",
            "risk_level": "LOW",
            "id_number": "330102199512016789",
            "country": "中国",
            "sanction_reason": "账户存在多次小额分散转入集中转出特征，需持续观察",
            "effective_date": date(2024, 1, 5),
        },
    ]


class Command(BaseCommand):
    help = "导入 OFAC / UN / EU / MPS / PBOC / INTERNAL 制裁名单样本数据"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="先清空现有制裁名单数据再导入",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = SanctionList.objects.all().delete()
            self.stdout.write(f"已清空 {deleted} 条制裁名单数据")

        data = get_data()
        created = 0
        skipped = 0

        for item in data:
            entity_name = item["entity_name"]
            list_type = item["list_type"]
            # 检查是否已存在同名+同名单类型的记录
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

        # 统计汇总
        total = SanctionList.objects.count()
        active = SanctionList.objects.filter(is_active=True).count()
        high_risk = SanctionList.objects.filter(risk_level="HIGH", is_active=True).count()

        self.stdout.write(f"  总计: {total} 条 | 有效: {active} 条 | 高风险: {high_risk} 条")
