# CapitalPay 客户门户 (Customer Portal)

Vue 3 + Vite + Element Plus 单页应用，面向 C 端终端用户：注册/登录、首次资料完善（Onboarding）、支付记录查询。同一套代码再起一个 Agent 进程。

## 前置条件

- Node.js 18+
- 后端 Django 服务运行在 `http://127.0.0.1:1024`（用户端 API 前缀 `/api/v1/user/`）

## 安装与启动

```bash
cd frontend/customer_portal
npm install
npm run dev:agent    # Agent     http://localhost:1026
npm run dev          # Customer  http://localhost:1027
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
| `/login` | Customer 进程上为客户登录；Agent 进程上为代理登录 |
| `/agent/login` | Agent 登录别名（Customer 进程会跳到 :1026） |
| `/onboarding` | 三步资料向导（基本信息 / 财务信息 / 证件） |
| `/remittance` | 汇款说明（用户端暂无在线汇款 API） |
| `/orders` | 支付历史 `GET /api/v1/user/payments/history/` |

## API 对接

- 认证：`/api/v1/user/auth/*`
- 资料：`/api/v1/user/onboarding/submit/`、`/status/`
- 支付：`/api/v1/user/payments/history/`

JWT 通过 axios 请求拦截器注入 `Authorization: Bearer <token>`，与 `client_portal` 保持一致。
