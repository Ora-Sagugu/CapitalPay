# B2B 支付系统 — Django 实现

基于 B2B 支付系统功能清单，使用 Python + Django + DRF 实现的完整 B2B 支付平台后端。

## 项目简介

本系统为 B2B（企业对企业）交易场景设计，覆盖从**预下单 → 汇款匹配 → 收款确认 → 退款处理 → 日终对账 → 清算结算**的完整资金链路。

### 核心业务流程

```
企业A下单 → 企业A银行汇款 → 平台自动匹配(UIN) → 确认收款 → 通知企业B
                                                          ↓
                                              日终对账 ← 银行对账单
                                                  ↓
                                           清算批次(扣手续费) → 结算到企业B
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | Django 4.2 + DRF 3.14 | MVT + Service Layer |
| 数据库 | SQLite | 本地 MVP 默认 |
| 缓存 | LocMemCache | OpenAPI nonce 防重放等 |
| 定时任务 | `manage.py run_scheduled_jobs` | 对账、清算、关单、通知重试 |
| 加密 | cryptography (Fernet) | 敏感字段透明加密 |
| API 鉴权 | HMAC-SHA256 | 商户接口签名验证 |

## 项目结构

```
b2b_payment_system/
├── b2b_payment/                # 项目配置 (settings / urls / wsgi)
├── apps/                       # 17 个业务 App
│   ├── core/                   # 基础层、仪表盘
│   ├── merchant/               # 商户 / KYC / 手续费
│   ├── payment/                # 支付订单 / 退款 / 银行网关
│   ├── account/                # Nostro / VA / 调拨 / 拨付
│   ├── reconciliation/         # 对账引擎
│   ├── settlement/             # 清算结算
│   ├── openapi/                # 商户 HMAC OpenAPI
│   ├── report/                 # 报表
│   ├── rbac/                   # 运营用户 / 角色 / 操作日志
│   ├── user_portal/            # 终端用户 / Onboarding
│   ├── agent/                  # 代理商 / 分润
│   ├── compliance/             # 制裁名单扫描
│   ├── routing/                # 银行通道 / 路由
│   ├── param/                  # 合作银行等参数
│   ├── adjustment/             # 调账申请
│   └── exchange/               # 汇率
├── frontend/client_portal/     # Vue3 运营后台
├── frontend/customer_portal/   # Vue3 客户端门户（注册/KYC）
├── docs/                       # 对接文档
├── manage.py
├── requirements.txt
└── .env.example
```

## 需要准备的软件

| 软件 | 是否必需 | 说明 |
|------|----------|------|
| Cursor / VS Code | 必需（二选一） | 写代码与开终端 |
| **Python 3.11 或 3.12** | 必需 | 勿用 3.14；本仓库已用 3.12 重建 `.venv` |
| **Node.js 18+** | 跑前端时必需 | 运营后台 Vite + Vue3 |
| Navicat Premium | 可选 | Navicat 可打开 `db.sqlite3` 看表 |

项目作为本地 MVP **可以运行、可以测**（约 70–75%）；银行出金/对账取数仍为 MOCK，不是生产上线完整度。

## 快速启动（Windows PowerShell，推荐）

本地默认 **SQLite**，不需要 PostgreSQL / Redis / Docker。

```powershell
# 1. 进入项目
cd d:\ProgramData\b2b_payment_system

# 2. 若尚无虚拟环境：用 uv 装 Python 3.12 并建 .venv（已建好可跳过）
# uv python install 3.12
# uv venv .venv --python 3.12
# uv pip install -r requirements.txt --python .\.venv\Scripts\python.exe

# 3. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 4. 迁移 + 演示数据（库已有数据时 seed 会报唯一约束，可改用 --reset）
$env:DJANGO_SETTINGS_MODULE = "b2b_payment.settings.local"
python manage.py migrate
python manage.py seed_data
# python manage.py seed_data --reset   # 需要清空重灌时再用
# python manage.py createsuperuser    # 首次无管理员时；现有库已有 admin

# 5. 启动后端（终端 1）
python manage.py runserver 8001

# 6. 启动运营后台（新开终端）
cd d:\ProgramData\b2b_payment_system\frontend\client_portal
npm install
npm run dev

# 7. 可选：启动客户端门户（新开终端，端口 9001）
cd d:\ProgramData\b2b_payment_system\frontend\customer_portal
npm install
npm run dev
```

| 地址 | 说明 |
|------|------|
| http://localhost:9000/ | 运营后台（Vite，`/api` 代理到 8001） |
| http://localhost:9001/ | 客户端门户（注册 / KYC / 订单） |
| http://127.0.0.1:8001/admin/ | Django Admin（已有用户 `admin`） |
| http://127.0.0.1:8001/api/docs/ | Swagger UI |
| http://127.0.0.1:8001/api/redoc/ | ReDoc |
| http://127.0.0.1:8001/api/schema/ | OpenAPI Schema |

Navicat：新建连接 → SQLite → 选择 `d:\ProgramData\b2b_payment_system\db.sqlite3`。

## 银行 / 汇率集成模式

默认全部为 `MOCK`（见 `.env.example`）。切换到真实渠道前需配置凭证，否则会显式失败（不会伪造成功出金）：

| 变量 | 取值 | 说明 |
|------|------|------|
| `BANK_GATEWAY_MODE` | MOCK / REAL | 支付、退款、转账、拨付网关 |
| `BANK_CODES` | 逗号分隔 | 注册的银行编码 |
| `BANK_RECON_FETCH_MODE` | MOCK / SFTP / API | 对账单拉取 |
| `BANK_FX_PROVIDER_MODE` | MOCK / REAL | 实时汇率源 |

## API 接口

### 对外接口（商户调用，HMAC 鉴权）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/payment/pre-order/` | 预下单 |
| GET | `/api/v1/payment/orders/` | 订单列表查询 |
| GET | `/api/v1/payment/orders/{order_no}/` | 单笔订单查询 |
| POST | `/api/v1/payment/orders/{order_no}/close/` | 关闭订单 |
| POST | `/api/v1/refund/apply/` | 退款申请 |
| GET | `/api/v1/refund/query/` | 退款查询 |

### 运营管理端（Session/Token 鉴权）

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/api/v1/admin/merchants/` | 商户管理 |
| CRUD | `/api/v1/admin/orders/` | 支付订单管理 |
| CRUD | `/api/v1/admin/refunds/` | 退款管理 |
| CRUD | `/api/v1/admin/recon-batches/` | 对账批次 |
| CRUD | `/api/v1/admin/recon-diffs/` | 对账差异 |
| CRUD | `/api/v1/admin/nostro-checks/` | Nostro 余额核对 |
| CRUD | `/api/v1/admin/settle-batches/` | 清算批次 |
| CRUD | `/api/v1/admin/settle-details/` | 清算明细 |
| CRUD | `/api/v1/admin/fee-shares/` | 手续费分润 |
| CRUD | `/api/v1/admin/difference-writeoffs/` | 差异代销账 |
| CRUD | `/api/v1/admin/nostro-accounts/` | Nostro 账户 |
| CRUD | `/api/v1/admin/fund-transfers/` | 资金调拨 |
| CRUD | `/api/v1/admin/user-payment-details/` | 用户支付明细 |
| CRUD | `/api/v1/admin/onboarding/` | 终端用户 Onboarding |
| CRUD | `/api/v1/admin/routing-logs/` | 路由日志（与操作日志分离） |
| GET | `/api/v1/admin/reports/merchant-daily/` | 商户日收单报表 |
| GET | `/api/v1/admin/reports/channel-fee/` | 渠道手续费报表 |
| GET | `/api/v1/admin/reports/platform-summary/` | 平台汇总表 |
| GET | `/api/v1/admin/reports/settle-batches/` | 结算批次报表 |
| GET | `/api/v1/admin/reports/settle-details/` | 结算明细报表 |

### HMAC 签名说明

商户调用对外接口需在 Header 中携带：

```
X-Api-Key:     商户 API Key
X-Timestamp:   请求时间戳 (Unix)
X-Nonce:       随机串 (防重放)
X-Signature:   HMAC-SHA256 签名
```

签名规则：参数按 key 字母序排序 → `key=value&...` → 追加 `&key={api_secret}` → HMAC-SHA256。

## 关键设计决策

| 决策 | 理由 |
|------|------|
| **Service Layer 模式** | 业务逻辑不放 View，因为同一逻辑被 OpenAPI / 运营后台 / 定时命令三个入口调用 |
| **Decimal 替代 float** | 金融场景 float 有精度丢失，Decimal 精确到分 |
| **select_for_update 行锁** | 资金操作防并发脏读 |
| **idempotency_key 幂等** | 防止网络重试导致重复下单 |
| **Fernet 透明加密** | 身份证号、银行账号等敏感字段加密存储 |
| **AuditLog append-only** | 审计日志只增不改，save() 时拦截更新 |
| **BankGateway 抽象层** | 不同银行网关实现统一接口，MockBankGateway 用于开发测试 |

## 运行测试

```powershell
cd d:\ProgramData\b2b_payment_system
.\.venv\Scripts\Activate.ps1
$env:DJANGO_SETTINGS_MODULE = "b2b_payment.settings.local"
python manage.py test -v2
# 或指定模块：
python manage.py test apps.payment.tests_gateway apps.settlement.tests apps.exchange.tests apps.reconciliation.tests -v2
```

测试覆盖：
- **Core / Merchant / Payment / RBAC / UserPortal**: 既有业务用例
- **Gateway / Settlement / Reconciliation / Exchange**: Mock 网关、清算划拨、对账取数、汇率 Provider

## 种子数据

```bash
# 填充演示数据
python manage.py seed_data

# 清空后重新填充
python manage.py seed_data --reset
```

填充的数据包括：
- 3 家商户（含 KYC、手续费、结算账户、支付产品配置）
- 3 个 Nostro 账户 + 1 笔资金调拨
- 6 个银行通道（含演示流水）
- 12 笔支付订单（覆盖所有状态：预创建/待收款/已收款/待清算/已清算/已关闭/已退款）
- 2 笔退款单（含已退款和待审核）
- 2 批对账（含差异记录和余额核对）
- 2 批清算（含明细、手续费分润、代销账）

## 定时任务

用 Django 管理命令手动触发（需要定时时可用 Windows 任务计划程序）：

```powershell
python manage.py run_scheduled_jobs --all
python manage.py run_scheduled_jobs --job close_expired_orders
```

| 任务 | 说明 |
|------|------|
| `close_expired_orders` | 关闭过期未支付订单 |
| `retry_failed_notifications` | 通知重试 |
| `run_daily_reconciliation` | 日终对账 |
| `check_nostro_balance` | Nostro 账户余额核对 |
| `run_daily_settlement` | 日终清算 |
| `suspend_expired_licenses` | 执照过期商户自动暂停 |
