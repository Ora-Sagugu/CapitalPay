"""对账引擎 — 交易匹配核心。

匹配策略（优先级从高到低）:
1. PRN 精确匹配 + 金额一致
2. bank_txn_id 精确匹配 + 金额一致
3. UIN 匹配（汇款附言中的 UIN）+ 金额一致
4. 金额 + 时间窗口模糊匹配 (±5 分钟)

PRN 提取: remark 中查找 "PRN:" 前缀的 6 位码（代理前缀 + 年积日 + 当日序号），
或独立的 6 位 PRN（如附言中只有 PRN 码）。
"""
from __future__ import annotations
import csv
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from django.utils import timezone
from apps.payment.models import PaymentOrder
from apps.payment.services.prn_service import extract_prn_from_remark, normalize_prn_code


@dataclass
class BankStatementLine:
    """银行对账单行。"""
    txn_id: str
    amount: Decimal
    txn_time: datetime
    txn_type: str  # CREDIT / DEBIT
    remark: str = ""
    prn_code: str | None = None  # 从 remark 提取的 PRN 码


@dataclass
class PlatformOrderLine:
    """平台订单行。"""
    order_no: str
    bank_txn_id: str | None
    amount: Decimal
    pay_received_at: datetime
    prn_code: str | None = None  # 订单关联的 PRN 码


@dataclass
class MatchResult:
    """对账匹配结果。"""
    matched: list = field(default_factory=list)
    bank_only: list = field(default_factory=list)      # 银行有平台无
    platform_only: list = field(default_factory=list)  # 平台有银行无
    amount_diff: list = field(default_factory=list)    # 金额不一致


@dataclass
class PrnMatchItem:
    """PRN 匹配记录。"""
    prn_code: str
    bank_line: BankStatementLine
    platform_order: PlatformOrderLine
    amount_matched: bool


class ReconciliationMatcher:
    """对账匹配引擎。"""

    TIME_WINDOW = timedelta(minutes=5)

    def match(
        self,
        bank_lines: list[BankStatementLine],
        platform_orders: list[PlatformOrderLine],
    ) -> MatchResult:
        """执行双向匹配。

        Args:
            bank_lines: 银行对账单行列表
            platform_orders: 平台订单列表

        Returns:
            MatchResult 包含 matched, bank_only, platform_only, amount_diff
        """
        result = MatchResult()

        # ── 索引构建 ──
        # bank_txn_id → bank_line
        bank_by_txn_id = {}
        for line in bank_lines:
            bank_by_txn_id[line.txn_id] = line

        # platform bank_txn_id → platform_order
        platform_by_txn_id = {}
        for order in platform_orders:
            if order.bank_txn_id:
                platform_by_txn_id[order.bank_txn_id] = order

        matched_platform_ids: set[str] = set()
        matched_bank_txn_ids: set[str] = set()

        # ── 第 1 轮: PRN 精确匹配 ──
        prn_results = self._match_by_prn(bank_lines, platform_orders)
        for item in prn_results:
            if item.amount_matched:
                result.matched.append({
                    "bank": item.bank_line,
                    "platform": item.platform_order,
                    "match_type": "PRN",
                    "prn_code": item.prn_code,
                })
                matched_platform_ids.add(item.platform_order.order_no)
                matched_bank_txn_ids.add(item.bank_line.txn_id)
            else:
                # PRN 匹配上但金额不一致 → 差异记录
                result.amount_diff.append({
                    "bank": item.bank_line,
                    "platform": item.platform_order,
                    "diff_type": "PRN_MISMATCH",
                    "prn_code": item.prn_code,
                })
                matched_platform_ids.add(item.platform_order.order_no)
                matched_bank_txn_ids.add(item.bank_line.txn_id)

        # ── 第 2 轮: bank_txn_id 精确匹配 ──
        remaining_bank = [l for l in bank_lines if l.txn_id not in matched_bank_txn_ids]
        remaining_platform = [o for o in platform_orders if o.order_no not in matched_platform_ids]

        for line in remaining_bank:
            if line.txn_id in platform_by_txn_id:
                order = platform_by_txn_id[line.txn_id]
                if order.order_no in matched_platform_ids:
                    continue
                if line.amount == order.amount:
                    result.matched.append({
                        "bank": line,
                        "platform": order,
                        "match_type": "EXACT",
                    })
                    matched_platform_ids.add(order.order_no)
                    matched_bank_txn_ids.add(line.txn_id)

        # ── 第 3 轮: 金额 + 时间窗口模糊匹配 ──
        remaining_bank_2 = [l for l in remaining_bank if l.txn_id not in matched_bank_txn_ids]
        remaining_platform_2 = [o for o in remaining_platform if o.order_no not in matched_platform_ids]

        for line in remaining_bank_2:
            matched = False
            for order in remaining_platform_2:
                if order.order_no in matched_platform_ids:
                    continue
                if line.amount == order.amount and self._in_time_window(line.txn_time, order.pay_received_at):
                    result.matched.append({
                        "bank": line,
                        "platform": order,
                        "match_type": "FUZZY",
                    })
                    matched_platform_ids.add(order.order_no)
                    matched_bank_txn_ids.add(line.txn_id)
                    matched = True
                    break

            if not matched:
                result.bank_only.append(line)

        # ── 识别 platform_only ──
        for order in platform_orders:
            if order.order_no not in matched_platform_ids:
                bank_same_txn = bank_by_txn_id.get(order.bank_txn_id) if order.bank_txn_id else None
                if bank_same_txn and bank_same_txn.amount != order.amount:
                    result.amount_diff.append({
                        "bank": bank_same_txn,
                        "platform": order,
                        "diff_type": "AMOUNT_DIFF",
                    })
                else:
                    result.platform_only.append(order)

        return result

    # ── PRN 匹配 ──────────────────────────────────────────

    def _match_by_prn(
        self,
        bank_lines: list[BankStatementLine],
        platform_orders: list[PlatformOrderLine],
    ) -> list[PrnMatchItem]:
        """PRN 码精确匹配。

        从银行流水 remark 中提取 PRN 码，与平台订单的 prn_code 精确比对。
        匹配规则:
        - 双方都有 PRN 码且一致 → 返回匹配项
        - 再判断金额是否一致 → amount_matched=True/False

        PRN 提取规则:
        - "PRN:A00101" / "PRNA00101" / "prn A00101" → A00101
        - remark 中独立的合法 6 位 PRN（前缀 + 001–366 + 01–99）
        """
        # 为银行流水提取 PRN
        bank_prn_index: dict[str, list[BankStatementLine]] = {}
        for line in bank_lines:
            prn = self._extract_prn(line.remark)
            if prn:
                line.prn_code = prn
                if prn not in bank_prn_index:
                    bank_prn_index[prn] = []
                bank_prn_index[prn].append(line)

        if not bank_prn_index:
            return []

        # 为平台订单建 PRN 索引
        platform_prn_index: dict[str, PlatformOrderLine] = {}
        for order in platform_orders:
            if order.prn_code:
                platform_prn_index[normalize_prn_code(order.prn_code)] = order

        if not platform_prn_index:
            return []

        # 交叉比对
        results: list[PrnMatchItem] = []
        matched_prns: set[str] = set()

        for prn, bank_list in bank_prn_index.items():
            platform_order = platform_prn_index.get(prn)
            if not platform_order:
                continue
            # 同一 PRN 有多笔银行流水时（重复打款），取第一笔匹配
            for bank_line in bank_list:
                if prn not in matched_prns:
                    amount_matched = bank_line.amount == platform_order.amount
                    results.append(PrnMatchItem(
                        prn_code=prn,
                        bank_line=bank_line,
                        platform_order=platform_order,
                        amount_matched=amount_matched,
                    ))
                    matched_prns.add(prn)
                    break

        return results

    @staticmethod
    def _extract_prn(remark: str) -> str | None:
        """从银行流水备注中提取 6 位 PRN 码。"""
        return extract_prn_from_remark(remark)

    # ── 辅助方法 ──────────────────────────────────────────

    def _in_time_window(self, t1: datetime, t2: datetime) -> bool:
        """判断两个时间是否在匹配窗口内。"""
        if t1.tzinfo:
            t1 = t1.replace(tzinfo=None)
        if t2 and t2.tzinfo:
            t2 = t2.replace(tzinfo=None)
        if not t2:
            return False
        return abs(t1 - t2) <= self.TIME_WINDOW

    # ── 数据提取 ──────────────────────────────────────────

    @staticmethod
    def parse_bank_csv(filepath: str) -> list[BankStatementLine]:
        """解析银行对账单 CSV 文件。

        CSV 列: txn_id, amount, txn_time, type, remark
        """
        lines = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                remark = row.get("remark", "")
                line = BankStatementLine(
                    txn_id=row.get("txn_id", ""),
                    amount=Decimal(row.get("amount", "0")),
                    txn_time=datetime.strptime(row["txn_time"], "%Y-%m-%d %H:%M:%S"),
                    txn_type=row.get("type", "CREDIT"),
                    remark=remark,
                )
                # 自动提取 PRN
                line.prn_code = ReconciliationMatcher._extract_prn(remark)
                lines.append(line)
        return lines

    @staticmethod
    def get_platform_orders(recon_date) -> list[PlatformOrderLine]:
        """提取平台端当日已收款的订单（含 PRN）。"""
        orders = PaymentOrder.objects.filter(
            pay_received_at__date=recon_date,
            status__in=[
                PaymentOrder.OrderStatus.PAY_RECEIVED,
                PaymentOrder.OrderStatus.PENDING_SETTLE,
                PaymentOrder.OrderStatus.SETTLED,
            ],
        ).only("order_no", "bank_txn_id", "amount", "pay_received_at", "prn_code")

        return [
            PlatformOrderLine(
                order_no=o.order_no,
                bank_txn_id=o.bank_txn_id,
                amount=o.amount,
                pay_received_at=o.pay_received_at,
                prn_code=o.prn_code,
            )
            for o in orders
        ]
