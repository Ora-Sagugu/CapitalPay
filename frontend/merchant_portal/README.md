# CapitalPay Merchant / Agent Portal

Vue 3 + Vite + Element Plus 单页应用。同一套代码起两个进程：

- Agent：`:1026`
- Merchant：`:1027`

Merchant 可注册/登录、完成 KYB、维护名下 Customer、发起汇款。Agent 管理名下 Merchant，只读查看 Customer。

## 前置条件

- Node.js 18+
- 后端 Django 服务运行在 `http://127.0.0.1:1024`（用户端 API 前缀 `/api/v1/user/`）

## 安装与启动

```bash
cd frontend/merchant_portal
npm install
npm run dev:agent    # Agent     http://localhost:1026
npm run dev          # Merchant  http://localhost:1027
```

Vite 将 `/api` 代理到 `http://127.0.0.1:1024`。占用目标端口时不会自动改号（`strictPort`）。

## 构建

```bash
npm run build
npm run preview
```

## 功能页面

| 路由 | 说明 |
|------|------|
| `/login` | Merchant 进程为商户登录；Agent 进程为代理登录 |
| `/agent/login` | Agent 登录别名（Merchant 进程会跳到 :1026） |
| `/onboarding` | 三步资料向导（基本信息 / 财务信息 / 证件） |
| `/customers` | Merchant 维护名下 Customer（KYC / 收款资料） |
| `/remittance` | 选定 Customer 后提交汇款 |
| `/orders` | 支付历史 `GET /api/v1/user/payments/history/` |

## API 对接

- 认证：`/api/v1/user/auth/*`
- 资料：`/api/v1/user/onboarding/submit/`、`/status/`
- 支付：`/api/v1/user/payments/history/`

JWT 通过 axios 请求拦截器注入 `Authorization: Bearer <token>`，与 `client_portal` 保持一致。
