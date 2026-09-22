"""Generate a cleaned Admin API inventory markdown from Django URL conf."""
from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "b2b_payment.settings.local")

import django

django.setup()

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "Admin_API_Inventory.md"

# Human-readable module titles for first path segment
MODULE_TITLES = {
    "auth": "认证",
    "users": "系统用户",
    "roles": "角色",
    "permissions": "权限",
    "functions": "功能点",
    "logs": "操作日志",
    "dashboard": "仪表盘",
    "merchants": "商户管理",
    "orders": "支付订单",
    "refunds": "退款",
    "bank-notifications": "银行入账通知",
    "onboarding": "终端用户 Onboarding",
    "end-users": "终端用户",
    "end-user-accounts": "终端用户账户",
    "end-user-payments": "终端用户支付",
    "agents": "代理",
    "agent-merchants": "代理-商户绑定",
    "agent-commissions": "代理佣金",
    "agent-kyc": "代理 KYC",
    "nostro-accounts": "Nostro 账户",
    "virtual-accounts": "虚拟账户",
    "fund-transfers": "资金调拨",
    "deposits": "充值申请",
    "disbursements": "代理出款",
    "user-payment-details": "用户收款明细",
    "channels": "银行通道",
    "rules": "路由规则",
    "routing-logs": "路由日志",
    "coop-banks": "合作银行",
    "fee-models": "费率模型",
    "bank-fee-configs": "银行费率配置",
    "risk-rating-limits": "风险评级限额",
    "remittance-fee-config": "汇款手续费配置",
    "sanction-lists": "制裁名单",
    "sanction-scans": "制裁扫描",
    "sanction-hits": "制裁命中",
    "recon-batches": "对账批次",
    "recon-diffs": "对账差异",
    "nostro-checks": "Nostro 余额核对",
    "recon-alerts": "对账告警",
    "recon-alert-config": "对账告警配置",
    "settle-batches": "清算批次",
    "settle-details": "清算明细",
    "fee-shares": "手续费分润",
    "difference-writeoffs": "差异核销",
    "applications": "调账申请",
    "exchange-rates": "汇率",
    "reports": "报表",
}

# Optional short descriptions keyed by exact path (suffix after /api/v1/admin/)
DESC = {
    "auth/login/": "运营后台登录，返回 JWT",
    "auth/logout/": "登出",
    "auth/me/": "当前登录用户信息",
    "dashboard/": "运营仪表盘汇总",
    "orders/stats/": "订单统计",
    "orders/trace-fund/": "资金链路追踪",
    "orders/sanction-check/": "订单制裁预检",
        "orders/preorders/": "预下单列表",
        "orders/preorder-stats/": "预下单统计",
        "orders/pending-transfers/": "待确认出款",
    "orders/apply/": "运营代下单",
    "orders/quote/": "汇款询价",
    "orders/fee_preview/": "手续费预览",
    "refunds/stats/": "退款统计",
    "refunds/fee-config/": "退款手续费配置（GET/PUT）",
    "bank-notifications/simulate/": "模拟银行入账通知",
    "merchants/remittance-options/": "汇款可选商户列表",
    "merchants/stats/": "商户统计",
    "agents/stats/": "代理统计",
    "applications/stats/": "调账统计",
    "deposits/stats/": "充值统计",
    "channels/stats/": "通道统计",
    "nostro-accounts/stats/": "Nostro 统计",
    "virtual-accounts/stats/": "VA 统计",
    "virtual-accounts/by-customer/": "按客户聚合 VA",
    "sanction-lists/stats/": "制裁名单统计",
    "sanction-lists/import-file/": "导入制裁名单文件",
    "exchange-rates/latest/": "最新汇率",
    "exchange-rates/batch-update/": "批量更新汇率",
    "exchange-rates/import_daily/": "导入日终汇率",
    "exchange-rates/sync_realtime/": "同步实时汇率",
    "exchange-rates/import-csv/": "CSV 导入汇率",
    "exchange-rates/convert/": "汇率换算",
    "exchange-rates/stats/": "汇率统计",
    "remittance-fee-config/": "全局汇款手续费（GET/PUT）",
    "recon-alert-config/update/": "更新对账告警配置",
}


def collect(patterns, prefix=""):
    rows = []
    for p in patterns:
        if isinstance(p, URLResolver):
            rows.extend(collect(p.url_patterns, prefix + str(p.pattern)))
        elif isinstance(p, URLPattern):
            path = prefix + str(p.pattern)
            if not path.startswith("api/v1/admin/"):
                continue
            callback = p.callback
            methods: list[str] = []
            if hasattr(callback, "actions"):
                methods = sorted({m.upper() for m in callback.actions.keys()})
            elif hasattr(callback, "cls"):
                cls = callback.cls
                methods = [
                    m.upper()
                    for m in ["get", "post", "put", "patch", "delete"]
                    if hasattr(cls, m)
                ]
            elif hasattr(callback, "view_class"):
                cls = callback.view_class
                methods = [
                    m.upper()
                    for m in ["get", "post", "put", "patch", "delete"]
                    if hasattr(cls, m)
                ]
            else:
                methods = ["?"]
            rows.append(("/" + path, methods))
    return rows


def clean_path(raw: str) -> str | None:
    if ".(?P<format>" in raw:
        return None
    path = raw
    if path.startswith("/api/v1/admin/^"):
        path = "/api/v1/admin/" + path[len("/api/v1/admin/^") :]
    path = path.replace("^", "")
    path = path.replace("$", "")
    path = re.sub(r"\(\?P<([^>]+)>\[[^\]]+\]\+\)", r"{\1}", path)
    if path in ("/api/v1/admin/", "/api/v1/admin"):
        return None
    if not path.endswith("/"):
        path += "/"
    return path


def action_desc(path: str) -> str:
    rest = path[len("/api/v1/admin/") :]
    if rest in DESC:
        return DESC[rest]
    # detail action by last segment
    parts = [p for p in rest.strip("/").split("/") if p]
    if not parts:
        return ""
    last = parts[-1]
    if last.startswith("{") and len(parts) == 2:
        return "详情"
    if len(parts) == 1:
        return ""  # filled by caller from HTTP methods
    mapping = {
        "review": "审核",
        "execute": "执行",
        "approve": "审批通过",
        "reject": "驳回",
        "cancel": "取消",
        "activate": "启用",
        "suspend": "停用",
        "close": "关闭",
        "deactivate": "停用",
        "revoke": "吊销",
        "recharge": "充值",
        "stats": "统计",
        "submit": "提交",
        "export": "导出",
        "query": "查询",
        "generate": "生成",
        "resolve": "处理差异",
        "ack": "确认告警",
        "write-off": "核销",
        "toggle-status": "切换状态",
        "reset-password": "重置密码",
        "assign-roles": "分配角色",
        "lock": "锁定",
        "unlock": "解锁",
        "grant": "授予权限",
        "capabilities": "能力配置",
        "permissions": "权限列表",
        "roles": "绑定角色",
        "detail": "详情",
        "start-review": "开始审核",
        "bind-merchant": "绑定商户",
        "unbind-merchant": "解绑商户",
        "delete": "删除（软删）",
        "kyc": "KYC",
        "fees": "费率",
        "settlement-accounts": "结算账户",
        "payment-products": "支付产品",
        "split-config": "分账配置",
        "pending-funds": "待结算资金",
        "settled-funds": "已结算资金",
        "pending-orders": "待结算订单",
        "settled-orders": "已结算订单",
        "settled-funds-export": "已结算资金导出",
        "settled-orders-export": "已结算订单导出",
        "review-kyc": "审核 KYC",
        "update-risk-level": "更新风险等级",
        "update-sanction-status": "更新制裁状态",
        "confirm-payment": "确认收款",
        "confirm-transfer": "确认出款",
        "pending-transfers": "待确认出款",
        "payout-banks": "出款银行列表",
        "sanction-review": "制裁审核详情",
        "refund-initiate": "发起退款",
        "notify-retry": "重试通知",
        "manual-confirm": "人工确认",
        "upload-contract": "上传合同",
        "fee-overview": "费用概览",
        "commissions": "佣金明细",
        "merchants": "下属商户",
        "health": "健康检查",
        "transactions": "流水",
        "scan": "发起扫描",
        "summary": "汇总",
        "trend": "趋势",
        "breakdowns": "维度拆解",
        "trace": "链路追踪",
        "list": "列表",
        "simulate": "模拟",
    }
    if last in mapping:
        return mapping[last]
    if last.startswith("{"):
        return "详情 / 更新 / 删除"
    return ""


def main():
    uniq: dict[str, set[str]] = {}
    for raw, methods in collect(get_resolver().url_patterns):
        path = clean_path(raw)
        if not path:
            continue
        uniq.setdefault(path, set()).update(methods)

    groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in sorted(uniq):
        rest = path[len("/api/v1/admin/") :]
        seg = rest.split("/")[0]
        # reports keep under reports
        if seg == "reports":
            key = "reports"
        else:
            key = seg
        methods = ",".join(sorted(uniq[path]))
        # refine list-only description
        desc = action_desc(path)
        if path.endswith(f"{seg}/") and methods == "GET":
            desc = desc or "列表"
        elif path.endswith(f"{seg}/") and "POST" in methods and "GET" in methods:
            desc = desc or "列表 / 创建"
        groups[key].append((methods, path, desc))

    lines = [
        "# CapitalPay 运营后台 API Inventory",
        "",
        "> Base path: `/api/v1/admin/`  ",
        "> Auth: JWT Bearer（登录除外）",
        "",
        "## 鉴权说明",
        "",
        "1. `POST /api/v1/admin/auth/login/` 获取 access token",
        "2. 后续请求头：`Authorization: Bearer <access_token>`",
        "3. 权限由 RBAC 角色 / 功能点控制，无权限返回 403",
        "",
        f"**接口总数：{len(uniq)}**",
        "",
    ]

    # order modules roughly by product area
    preferred = [
        "auth",
        "dashboard",
        "users",
        "roles",
        "permissions",
        "functions",
        "logs",
        "merchants",
        "onboarding",
        "end-users",
        "end-user-accounts",
        "end-user-payments",
        "orders",
        "refunds",
        "bank-notifications",
        "agents",
        "agent-merchants",
        "agent-commissions",
        "agent-kyc",
        "nostro-accounts",
        "virtual-accounts",
        "fund-transfers",
        "deposits",
        "disbursements",
        "user-payment-details",
        "channels",
        "rules",
        "routing-logs",
        "coop-banks",
        "fee-models",
        "bank-fee-configs",
        "risk-rating-limits",
        "remittance-fee-config",
        "sanction-lists",
        "sanction-scans",
        "sanction-hits",
        "recon-batches",
        "recon-diffs",
        "nostro-checks",
        "recon-alerts",
        "recon-alert-config",
        "settle-batches",
        "settle-details",
        "fee-shares",
        "difference-writeoffs",
        "applications",
        "exchange-rates",
        "reports",
    ]
    ordered = [k for k in preferred if k in groups] + [
        k for k in sorted(groups) if k not in preferred
    ]

    for key in ordered:
        title = MODULE_TITLES.get(key, key)
        lines.append(f"## {title} (`/{key}/`)")
        lines.append("")
        lines.append("| Method | Path | 说明 |")
        lines.append("| ------ | ---- | ---- |")
        for methods, path, desc in groups[key]:
            lines.append(f"| {methods} | `{path}` | {desc} |")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(uniq)} endpoints)")


if __name__ == "__main__":
    main()
