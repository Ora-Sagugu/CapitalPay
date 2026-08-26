"""生成手续费分润记录。

为已有的 SettlementDetail 生成 FeeShare 记录。
适用场景: 历史数据回填 / 新模型字段迁移后数据补齐。
"""
from django.core.management.base import BaseCommand
from apps.settlement.models import SettlementDetail, FeeShare
from apps.settlement.engine.calculator import SettlementCalculator


class Command(BaseCommand):
    help = "为已有清算明细生成手续费分润记录"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-no",
            type=str,
            help="指定清算批次号（不传则处理所有）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="预览模式，不实际写入",
        )

    def handle(self, *args, **options):
        batch_no = options["batch_no"]
        dry_run = options["dry_run"]

        qs = SettlementDetail.objects.filter(is_deleted=False)
        if batch_no:
            qs = qs.filter(batch__batch_no=batch_no)

        total = qs.count()
        existing = FeeShare.objects.filter(
            settlement_detail__in=qs, is_deleted=False
        ).count()
        to_create = total - existing

        self.stdout.write(f"清算明细总数: {total}")
        self.stdout.write(f"已有分润记录: {existing}")
        self.stdout.write(f"待生成: {to_create}")

        if to_create == 0:
            self.stdout.write(self.style.SUCCESS("所有分润记录已存在，无需生成"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] 将生成 {to_create} 条记录，未实际写入"))
            return

        calculator = SettlementCalculator()
        detail_ids = list(
            qs.exclude(id__in=FeeShare.objects.filter(is_deleted=False).values("settlement_detail_id"))
            .values_list("id", flat=True)
        )

        created = 0
        failed = 0
        for detail_id in detail_ids:
            try:
                detail = SettlementDetail.objects.get(id=detail_id)
                calculator.calculate_fee_share(detail)
                created += 1
                if created % 50 == 0:
                    self.stdout.write(f"  进度: {created}/{to_create}")
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  失败 detail_id={detail_id}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"完成! 成功: {created}, 失败: {failed}"
        ))
