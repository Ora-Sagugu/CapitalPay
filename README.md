# CapitalPay

基于 Django REST Framework 与 Vue 3 的支付平台（**CapitalPay**），覆盖预下单、汇款匹配、收款确认、退款、对账和清算结算。

## 角色与余额

对外角色统一称 **Agent / Customer / Bank**（代码标识不变：`agent` / `customer` / `bank` / `merchant` 等）。

| 对外称呼 | 是谁 | 不是谁 |
| --- | --- | --- |
| **Agent** | 代客操作方，替名下 Customer 办业务 | 不是收款方 |
| **Customer** | 资金所有人；指定最终收款账户 | — |
| **Bank** | 资金通道（本阶段 Mock / 测试数据） | 本地不查银行实金 |
| **CapitalPay** | 平台：记账、审核、按指令付出 | — |

**余额只认系统账面**（System book），不是银行余额。收款方 = Customer 指定的外部账户，不是 Agent。

**主路径（本地）：** Customer 系统账面有余额 → Agent（或 Customer）提交转账 → CapitalPay 审核 → Mock 付出并扣 Customer 账面。

## 项目简介

覆盖从**预下单 → 汇款匹配 → 收款确认 → 退款处理 → 日终对账 → 清算结算**的完整资金链路（银行侧本阶段为 Mock）。

### 核心业务流程

```
Customer/Agent 下单 →（Mock）入金记系统账面 → CapitalPay 匹配(PRN)/确认
                                                          ↓
                                              日终对账 ← Mock 对账单
                                                  ↓
                              清算批次(扣手续费) → Mock 付出到收款方账户
```

## 技术栈


| 组件     | 技术                             | 说明                  |
| ------ | ------------------------------ | ------------------- |
| Web 框架 | Django 4.2 + DRF 3.14          | MVT + Service Layer |
| 数据库    | SQLite / MySQL 8.0             | 本地默认 SQLite；生产 MySQL 8.0（utf8mb4） |
| 缓存     | LocMemCache                    | OpenAPI nonce 防重放等  |
| 定时任务   | `manage.py run_scheduled_jobs` | 对账、清算、关单、通知重试       |
| 加密     | cryptography (Fernet)          | 敏感字段透明加密            |
| API 鉴权 | HMAC-SHA256                    | 商户接口签名验证            |
| 网关     | nginx                          |                     |




## 项目结构

```
CapitalPay/
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
├── frontend/customer_portal/   # Vue3 Agent / Customer 门户（注册/KYC）
├── deploy/                     # 阿里云安装、Nginx、systemd
├── scripts/                    # 本地启停与部署入口
├── manage.py
├── requirements.txt
└── .env.example
```

详细说明每个目录、前后端页面与后端模块的对应关系，见 **[docs/系统文件导览.md](docs/系统文件导览.md)**。

## 运行与维护

本地可用根目录 `START_PROJECT.bat` / `STOP_PROJECT.bat` 一键启停（后端 `:1024`、运营后台 `:1025`、Agent `:1026`、Customer `:1027`）。本地默认使用 SQLite 与 LocMemCache，无需 Docker、Redis 或 Celery；生产使用 MySQL 8.0（可设 `MYSQL_HOST` 在本地联调）。

### 演示数据（推荐首次启动后执行）

灌入非洲走廊演示数据（商户、代理、订单、银行通道、对账/清算、门户账号等）：

```bash
python manage.py seed_data --reset
```

不加 `--reset` 时若库中已有业务数据可能因唯一约束失败；演示前建议带 `--reset`（会清空业务数据，保留 OFAC/UN 制裁名单）。

| 入口 | 账号 | 密码 | 说明 |
| ---- | ---- | ---- | ---- |
| [运营后台 :1025](http://localhost:1025/) | `admin` | `123456` | Super Admin（另有 maker/checker/authoriser，密码同） |
| [Agent :1026](http://localhost:1026/login) | `GraceNyambura@gmail.com` | `123456` | EastAfrica Collection（Horizon + Savannah + Kilimanjaro，多客户 / 资金 / Agent Fee 历史） |
| Agent | `AdewaleBalogun@gmail.com` | `123456` | Sahel Corridor（下属 Lagos Agro，3 名顾客） |
| Agent | `AmaSerwaa@gmail.com` | `123456` | Gulf Coast Collections（下属 Cape Coast Export，3 名顾客） |
| [Customer :1027](http://localhost:1027/login) | `DanielOchieng@gmail.com` | `123456` | Horizon Trade（Grace 下属） |
| Customer | `MaryAchieng@gmail.com` | `123456` | Savannah Imports（Grace 下属） |
| Customer | `ChiomaEze@gmail.com` | `123456` | Lagos Agro（Adewale 下属） |
| Customer | `KwameAsante@gmail.com` | `123456` | Cape Coast Export（Ama 下属） |

门户邮箱注册/登录仅允许 `@gmail.com`；完整名单见 [`docs/账户和密码.md`](docs/账户和密码.md)。

短信验证码演示固定为 `000000`。

演示流程提示：Agent Orders 有待审客户汇款；运营 Orders 有待 CapitalPay 同意的申请；`PAYDEMOPAYOUT01` 已到 `PENDING_PAY`，Confirm transfer 时 ICBC 费率最低但 USD 余额不足，瀑布会推荐下一家银行。

### 启动后入口

| 地址 | 用途 |
| ---- | ---- |
| [http://localhost:1025/](http://localhost:1025/) | 运营后台（内置账号 `admin` / `123456`，不可注册） |
| [http://localhost:1026/login](http://localhost:1026/login) | Agent 注册 / 登录 |
| [http://localhost:1027/login](http://localhost:1027/login) | Customer 注册 / 登录 |

### 后端辅助地址

| 地址 | 用途 |
| ---- | ---- |
| `http://127.0.0.1:1024/admin/` | Django Admin |
| `http://127.0.0.1:1024/api/docs/` | Swagger UI |
| `http://127.0.0.1:1024/api/schema/` | OpenAPI Schema |




## 银行 / 汇率集成模式

**银行 API 形态未知：本阶段不做银行侧详细设计，只保留网关/对账等 API 占位。**  
CapitalPay 侧银行相关一律走 **Mock + 种子/测试数据**（通道余额、合作银行、费率等），余额只认系统账面。

默认全部为 `MOCK`（见 `.env.example`）。切到 `REAL` / SFTP / API 前需真实凭证，否则会显式失败（不会伪造成功出金）：


| 变量                      | 取值                | 说明            |
| ----------------------- | ----------------- | ------------- |
| `BANK_GATEWAY_MODE`     | MOCK / REAL       | 支付、退款、转账、拨付网关 |
| `BANK_CODES`            | 逗号分隔              | 注册的银行编码       |
| `BANK_RECON_FETCH_MODE` | MOCK / SFTP / API | 对账单拉取         |
| `BANK_FX_PROVIDER_MODE` | MOCK / REAL       | 实时汇率源         |




## API 接口

交互式 schema 见运行中的 `/api/docs/`。

### 商户接口（HMAC）


| 方法   | 路径                                         | 说明     |
| ---- | ------------------------------------------ | ------ |
| POST | `/api/v1/payment/pre-order/`               | 预下单    |
| GET  | `/api/v1/payment/orders/`                  | 订单列表查询 |
| GET  | `/api/v1/payment/orders/{order_no}/`       | 单笔订单查询 |
| POST | `/api/v1/payment/orders/{order_no}/close/` | 关闭订单   |
| POST | `/api/v1/refund/apply/`                    | 退款申请   |
| GET  | `/api/v1/refund/query/`                    | 退款查询   |




### 代理 PRN 接口（HMAC）

代理使用自身 `api_key` / `api_secret`，签名规则与商户一致。


| 方法   | 路径                              | 说明                                                                     |
| ---- | ------------------------------- | ---------------------------------------------------------------------- |
| POST | `/api/v1/agent/prn/apply/`      | 签发 PRN；可传 `merchant_no`、`amount`、`currency`、`reference`、`expire_hours` |
| GET  | `/api/v1/agent/prn/{prn_code}/` | 查询 PRN；状态为 `ISSUED`、`BOUND`、`MATCHED` 或 `EXPIRED`                      |




### 运营管理接口（JWT）

登录入口为 `POST /api/v1/admin/auth/login/`，其余商户、订单、退款、账户、代理、合规、对账、清算与报表接口均位于 `/api/v1/admin/`。

### HMAC 签名说明

请求头：

```
X-Api-Key: <api_key>
X-Timestamp: <Unix 秒>
X-Nonce: <单次随机串>
X-Signature: <小写十六进制摘要>
```

签名原文必须与服务端一致：

```text
api_key + timestamp + nonce + METHOD + path + [?sorted_query] + [raw_body]
```

- `METHOD` 使用大写；`path` 不含 query。
- Query 按 key 升序拼成 `k=v&...`，存在时前置 `?`。
- Body 使用实际发送的原始字节文本，不能在签名后重新格式化 JSON。
- 以 `api_secret` 为 key 计算 HMAC-SHA256；时间戳有效期为 ±300 秒，nonce 在窗口内不可复用。



## 关键设计决策


| 决策                       | 理由                                              |
| ------------------------ | ----------------------------------------------- |
| **Service Layer 模式**     | 业务逻辑不放 View，因为同一逻辑被 OpenAPI / 运营后台 / 定时命令三个入口调用 |
| **Decimal 替代 float**     | 金融场景 float 有精度丢失，Decimal 精确到分                   |
| **select_for_update 行锁** | 资金操作防并发脏读                                       |
| **idempotency_key 幂等**   | 防止网络重试导致重复下单                                    |
| **Fernet 透明加密**          | 身份证号、银行账号等敏感字段加密存储                              |
| **AuditLog append-only** | 审计日志只增不改，save() 时拦截更新                           |
| **BankGateway 抽象层**      | 不同银行网关实现统一接口，MockBankGateway 用于开发测试             |




## 制裁名单（OFAC / UN）

首次部署或本地初始化时，导入官方全量制裁名单：

```bash
python manage.py import_all_sanctions --download --reset
```

仅更新（不清库）：

```bash
python manage.py import_all_sanctions --download
```

定时任务（可加入 crontab）：

```bash
python manage.py run_scheduled_jobs --job refresh_sanction_lists
```

汇款页收款人姓名/地址输入时会调用 `POST /api/v1/user/payments/sanction-check/` 做实时警告（如 Iran、North Korea）；精确命中 SDN 实体姓名时提交仍会被拦截。