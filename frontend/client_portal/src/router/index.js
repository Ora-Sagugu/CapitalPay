import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layout/DefaultLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '仪表盘' } },
      // 汇款服务
      { path: 'remittance-apply', name: 'remittance-apply', component: () => import('@/views/RemittanceApply.vue'), meta: { title: '汇款申请' } },
      { path: 'orders', name: 'orders', component: () => import('@/views/Orders.vue'), meta: { title: '汇款管理' } },
      { path: 'pre-settlement', name: 'pre-settlement', component: () => import('@/views/PreSettlement.vue'), meta: { title: '预清算管理' } },
      { path: 'fund-trace', name: 'fund-trace', component: () => import('@/views/FundTrace.vue'), meta: { title: '资金追踪' } },
      { path: 'refunds', name: 'refunds', component: () => import('@/views/Refunds.vue'), meta: { title: '退款查询' } },
      { path: 'exchange-rates', name: 'exchange-rates', component: () => import('@/views/ExchangeRates.vue'), meta: { title: '汇率管理' } },
      { path: 'reconciliation', name: 'reconciliation', component: () => import('@/views/Reconciliation.vue'), meta: { title: '对账管理' } },
      // 客户
      { path: 'merchants', name: 'merchants', component: () => import('@/views/Merchants.vue'), meta: { title: '客户管理' } },
      { path: 'deposits', name: 'deposits', component: () => import('@/views/Deposits.vue'), meta: { title: '入账管理' } },
      { path: 'virtual-accounts', name: 'virtual-accounts', component: () => import('@/views/VirtualAccounts.vue'), meta: { title: '账户管理' } },
      { path: 'user-portal', name: 'user-portal', component: () => import('@/views/UserPortalAdmin.vue'), meta: { title: '终端用户' } },
      // 代理
      { path: 'agents', name: 'agents', component: () => import('@/views/Agents.vue'), meta: { title: '代理尽调' } },
      { path: 'agent-extras', name: 'agent-extras', component: () => import('@/views/AgentExtras.vue'), meta: { title: '代理分润配置' } },
      // 账户资金
      { path: 'fund-transfers', name: 'fund-transfers', component: () => import('@/views/FundTransfers.vue'), meta: { title: '资金调拨' } },
      { path: 'account-extras', name: 'account-extras', component: () => import('@/views/AccountExtras.vue'), meta: { title: '账户其他' } },
      { path: 'settlement', name: 'settlement', component: () => import('@/views/Settlement.vue'), meta: { title: '结算分润' } },
      { path: 'adjustments', name: 'adjustments', component: () => import('@/views/Adjustments.vue'), meta: { title: '调账管理' } },
      // 合规银行
      { path: 'compliance', name: 'compliance', component: () => import('@/views/Compliance.vue'), meta: { title: '制裁名单扫描' } },
      { path: 'channels', name: 'channels', component: () => import('@/views/Channels.vue'), meta: { title: '银行通道' } },
      { path: 'params', name: 'params', component: () => import('@/views/Params.vue'), meta: { title: '参数配置' } },
      // 报表 / 系统
      { path: 'reports', name: 'reports', component: () => import('@/views/Reports.vue'), meta: { title: '报表服务' } },
      { path: 'system-users', name: 'system-users', component: () => import('@/views/SystemUsers.vue'), meta: { title: '系统设置' } }
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFound.vue'), meta: { public: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
