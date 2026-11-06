# CapitalPay

**B2B 跨境汇款 / 支付清算平台（演示项目）**

基于 **Django REST Framework + Vue 3** 实现的端到端资金链路：预下单 → 入金记账 → PRN 匹配 → 运营审核 → 退款 → 日终对账 → 清算结算。银行侧本阶段为 **Mock**，余额一律以 **系统账面（System Book）** 为准。

> 适合作为后端：覆盖金融系统中的幂等、并发控制、对账清算、HMAC OpenAPI、RBAC、制裁名单等真实工程问题。

---

## 亮点

| 维度 | 做了什么 |
| --- | --- |
| **领域建模** | Agent / Merchant / Customer / Bank / Platform 角色清晰拆分，账面与银行实金解耦 |
| **资金安全** | `Decimal` 金额、`select_for_update` 行锁、`idempotency_key` 防重下单 |
| **开放接口** | 商户 / 代理 HMAC-SHA256 签名（时间窗 + nonce 防重放） |
| **运营能力** | JWT + 功能权限（RBAC）、订单审核、对账、清算、报表 |
| **合规** | OFAC / UN 制裁名单导入与汇款前实时筛查 |
| **可演进集成** | `BankGateway` 抽象层，`MOCK` / `REAL` 可切换，未配置凭证时显式失败（不伪造成功出金） |
| **工程结构** | Service Layer：同一业务被 OpenAPI、运营后台、定时任务复用 |

---

## 角色与资金模型

| 角色 | 职责 | 边界 |
| --- | --- | --- |
| **Agent** | 门户登录；持有 CURRENT / FEE 系统账面；通过 **Agent Code** 挂载并管理 **Merchant**；只读查看名下 Merchant 的 **Customer** | 不是最终收款方；不代客创建/编辑 Customer；不代客发起汇款 |
| **Merchant** | 独立登录；自有 VA / 钱包；注册须绑定 Agent Code；名下维护 **Customer** | 汇款从自己的系统账面支出 |
| **Customer** | Merchant 名下 KYC / 收款资料，下单时必选 | 无登录、无 VA；由 Merchant 管理，Agent 可只读查看 |
| **Bank** | 资金通道（Mock / 种子数据） | 本地不查真实银行余额 |
| **CapitalPay** | 平台：记账、审核、按指令 Mock 付出 | — |

**主路径：** Merchant CURRENT 账面有余额 → 选定 Customer 提交汇款 → CapitalPay 审核 → Mock 付出并扣减对应账面。

```
Merchant 下单 → Mock 入金记系统账面 → PRN 匹配 / 运营确认
                                              ↓
                                   日终对账 ← Mock 对账单
                                              ↓
                         清算批次（扣手续费）→ Mock 付出到收款方账户
```

---

## 技术栈

| 层级 | 技术 | 说明 |
| --- | --- | --- |
| 后端 | Django 4.2 · DRF 3.14 · JWT / HMAC | MVT + Service Layer |
| 前端 | Vue 3 · Vite · Element Plus · Pinia · Vue I18n | 运营后台 + Agent / Merchant 双门户 |
| 数据 | SQLite（本地） / MySQL 8.0（生产） | utf8mb4 |
| 任务 | `manage.py run_scheduled_jobs` | 对账、清算、关单、制裁名单刷新、通知重试 |
| 安全 | Fernet 字段加密 · AuditLog 只增不改 · CORS / 签名校验 | 敏感字段（证件号、账号等）落库加密 |
| 文档 | drf-spectacular | Swagger：`/api/docs/` |

本地默认 **无需 Docker / Redis / Celery**（LocMemCache）。

---

## 仓库结构

```
CapitalPay/
├── b2b_payment/                 # Django 配置
├── apps/                        # 业务模块（按领域拆分）
│   ├── payment/                 # 订单 / 退款 / 银行网关
│   ├── account/                 # Nostro / VA / 调拨
│   ├── reconciliation/          # 对账引擎
│   ├── settlement/              # 清算结算
│   ├── openapi/                 # 商户 HMAC OpenAPI
│   ├── routing/                 # 银行通道与智能路由
│   ├── compliance/              # 制裁名单
│   ├── agent/ · merchant/       # 代理 / 商户
│   ├── rbac/ · user_portal/     # 运营权限 / 终端门户
│   └── report/ · exchange/ …    # 报表、汇率等
├── frontend/
│   ├── client_portal/           # 运营后台  :1025
│   └── merchant_portal/         # Agent :1026 · Merchant :1027
├── deploy/ · scripts/           # 部署与本地启停
├── manage.py
├── requirements.txt
└── .env.example
```

---

## 关键设计决策

| 决策 | 原因 |
| --- | --- |
| **Service Layer** | 业务不写在 View 里，OpenAPI / 后台 / 定时任务共用同一套逻辑 |
| **Decimal，不用 float** | 金融金额需要精确到分 |
| **`select_for_update`** | 资金读写防并发脏写 |
| **`idempotency_key`** | 网络重试不导致重复下单 |
| **Fernet 透明加密** | 证件号、银行账号等敏感字段加密存储 |
| **AuditLog append-only** | 审计只增不改，拦截 `save()` 更新 |
| **BankGateway 抽象** | 统一网关接口；开发用 `MockBankGateway`，上线可换真实实现 |

---

## 快速开始

### 环境

- Python 3.10+（推荐使用项目 `.venv`）
- Node.js 18+（前端）

```bash
# 后端
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # 或按需修改
python manage.py migrate
python manage.py seed_data --reset
python manage.py seed_exhibition_tom_amy

# 可选：导入 OFAC / UN 制裁名单
python manage.py import_all_sanctions --download --reset
```

Windows 可用根目录 **`START_PROJECT.bat` / `STOP_PROJECT.bat`** 一键启停：

| 服务 | 端口 |
| --- | --- |
| 后端 API | `:1024` |
| 运营后台 | `:1025` |
| Agent 门户 | `:1026` |
| Merchant 门户 | `:1027` |

### 演示账号

| 入口 | 账号 | 密码 | 说明 |
| --- | --- | --- | --- |
| [运营后台](http://localhost:1025/) | `admin` | `123456` | Super Admin（另有 ops / compliance / finance 等，密码同） |
| [Agent](http://localhost:1026/login) | `TomLee@gmail.com` | `123456` | 展览演示 Agent |
| [Merchant](http://localhost:1027/login) | `AmyFox@gmail.com` | `123456` | 展览演示 Merchant |

- 门户可用任意有效邮箱注册（大小写不敏感）
- 短信验证码演示固定：`000000`
- Merchant 汇款：先建 Customer，再选客户下单，进入运营审核

### API 文档

| 地址 | 用途 |
| --- | --- |
| http://127.0.0.1:1024/api/docs/ | Swagger UI |
| http://127.0.0.1:1024/api/schema/ | OpenAPI Schema |
| http://127.0.0.1:1024/admin/ | Django Admin |

---

## API 概览

### 商户 OpenAPI（HMAC）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/payment/pre-order/` | 预下单 |
| GET | `/api/v1/payment/orders/` | 订单列表 |
| GET | `/api/v1/payment/orders/{order_no}/` | 订单详情 |
| POST | `/api/v1/payment/orders/{order_no}/close/` | 关单 |
| POST | `/api/v1/refund/apply/` | 退款申请 |
| GET | `/api/v1/refund/query/` | 退款查询 |

### 代理 PRN（HMAC）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/agent/prn/apply/` | 签发 PRN |
| GET | `/api/v1/agent/prn/{prn_code}/` | 查询 PRN |

### 运营后台（JWT）

`POST /api/v1/admin/auth/login/`，业务接口统一挂在 `/api/v1/admin/`（商户、订单、账户、对账、清算、报表、合规等）。

### HMAC 签名

请求头：`X-Api-Key` · `X-Timestamp` · `X-Nonce` · `X-Signature`

```text
签名原文 = api_key + timestamp + nonce + METHOD + path + [?sorted_query] + [raw_body]
摘要 = HMAC-SHA256(api_secret, 原文)  → 小写 hex
```

时间窗 ±300 秒；nonce 在窗口内不可复用。Body 必须用实际发送的原始字节，签名后不可再格式化 JSON。

---

## 银行 / 汇率集成模式

银行 API 形态未定：本阶段只保留网关与对账等**占位**，默认全部 `MOCK`（见 `.env.example`）。

| 变量 | 取值 | 说明 |
| --- | --- | --- |
| `BANK_GATEWAY_MODE` | `MOCK` / `REAL` | 支付、退款、转账、拨付 |
| `BANK_RECON_FETCH_MODE` | `MOCK` / `SFTP` / `API` | 对账单拉取 |
| `BANK_FX_PROVIDER_MODE` | `MOCK` / `REAL` | 实时汇率 |

切到真实模式前必须配置凭证，否则会**显式失败**，避免「假成功出金」。

---

## 制裁名单

```bash
# 全量导入（下载 + 重置）
python manage.py import_all_sanctions --download --reset

# 仅更新
python manage.py import_all_sanctions --download

# 定时刷新
python manage.py run_scheduled_jobs --job refresh_sanction_lists
```

汇款页会对收款人姓名 / 地址做实时警告（`POST /api/v1/user/payments/sanction-check/`）；精确命中 SDN 实体时提交会被拦截。

---

## 说明

本仓库为 **可运行的教学 / 面试演示系统**，重点展示支付清算领域的业务拆分与工程实践，**不构成生产投产方案**。生产环境需补齐真实银行对接、密钥管理、高可用与审计合规等能力。

如需了解模块细节，建议从 `apps/payment/`、`apps/account/`、`apps/reconciliation/`、`apps/settlement/` 与 `frontend/*/src/views/` 入手。
