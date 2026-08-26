# Techtanium 客户门户 (Customer Portal)

Vue 3 + Vite + Element Plus 单页应用，面向 C 端终端用户：注册/登录、首次资料完善（Onboarding）、支付记录查询。

## 前置条件

- Node.js 18+
- 后端 Django 服务运行在 `http://127.0.0.1:8001`（用户端 API 前缀 `/api/v1/user/`）

## 安装与启动

```bash
cd frontend/customer_portal
npm install
npm run dev
```

开发服务器默认端口 **9001**，浏览器访问 [http://localhost:9001](http://localhost:9001)。

Vite 将 `/api` 代理到 `http://127.0.0.1:8001`。

## 构建

```bash
npm run build
npm run preview
```

## 功能页面

| 路由 | 说明 |
|------|------|
| `/login` | 手机号/邮箱注册与登录，支持短信验证码 |
| `/onboarding` | 三步资料向导（基本信息 / 财务信息 / 证件） |
| `/remittance` | 汇款说明（用户端暂无在线汇款 API） |
| `/orders` | 支付历史 `GET /api/v1/user/payments/history/` |

## API 对接

- 认证：`/api/v1/user/auth/*`
- 资料：`/api/v1/user/onboarding/submit/`、`/status/`
- 支付：`/api/v1/user/payments/history/`

JWT 通过 axios 请求拦截器注入 `Authorization: Bearer <token>`，与 `client_portal` 保持一致。
