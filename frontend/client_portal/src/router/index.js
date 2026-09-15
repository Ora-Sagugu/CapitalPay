import { createRouter, createWebHistory } from 'vue-router'
import { canAccessPath, firstAllowedPath } from '@/config/functions'

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
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: 'Overview', titleKey: 'menu.dashboard', permission: 'feature:dashboard' } },
      { path: 'roles', name: 'roles', component: () => import('@/views/Roles.vue'), meta: { title: 'Roles', titleKey: 'menu.roles', permission: 'feature:roles' } },
      { path: 'users', name: 'users', component: () => import('@/views/Users.vue'), meta: { title: 'Users', titleKey: 'menu.users', permission: 'feature:users' } },
      { path: 'risk-rating', name: 'risk-rating', component: () => import('@/views/RiskRating.vue'), meta: { title: 'Risk Rating', titleKey: 'menu.riskRating', permission: 'feature:risk_rating' } },
      { path: 'remittance-fees', name: 'remittance-fees', component: () => import('@/views/RemittanceFees.vue'), meta: { title: 'Remittance Fee', titleKey: 'menu.remittanceFees', permission: 'feature:remittance_fees' } },
      { path: 'kyc', redirect: { path: '/merchants', query: { tab: 'kyc' } } },
      { path: 'merchants', name: 'merchants', component: () => import('@/views/Merchants.vue'), meta: { title: 'Profiles', titleKey: 'menu.merchants', permission: 'feature:merchants' } },
      { path: 'accounts', name: 'accounts', component: () => import('@/views/Accounts.vue'), meta: { title: 'Master Account', titleKey: 'menu.accounts', permission: 'feature:accounts' } },
      { path: 'virtual-accounts', name: 'virtual-accounts', component: () => import('@/views/VirtualAccounts.vue'), meta: { title: 'Virtual Accounts', titleKey: 'menu.virtualAccounts', permission: 'feature:virtual_accounts' } },
      { path: 'deposits', name: 'deposits', component: () => import('@/views/Deposits.vue'), meta: { title: 'Deposits', titleKey: 'menu.deposits', permission: 'feature:deposits' } },
      { path: 'wallet', name: 'wallet', component: () => import('@/views/Wallet.vue'), meta: { title: 'Wallet', titleKey: 'menu.wallet', permission: 'feature:wallet' } },
      { path: 'profile-review', redirect: { path: '/merchants', query: { tab: 'kyc' } } },
      { path: 'agents', name: 'agents', component: () => import('@/views/Agents.vue'), meta: { title: 'Profiles', titleKey: 'menu.agents', permission: 'feature:agents' } },
      { path: 'agent-fees', name: 'agent-fees', component: () => import('@/views/AgentFees.vue'), meta: { title: 'Agent Fee', titleKey: 'menu.agentFees', permission: 'feature:agent_fees' } },
      { path: 'agent-fees/:id', name: 'agent-fee-detail', component: () => import('@/views/AgentFeeDetail.vue'), meta: { title: 'Agent Fee', titleKey: 'menu.agentFees', permission: 'feature:agent_fees' } },
      { path: 'disbursements', name: 'disbursements', component: () => import('@/views/Disbursements.vue'), meta: { title: 'Disbursements', titleKey: 'menu.disbursements', permission: 'feature:disbursements' } },
      { path: 'exchange-rates', name: 'exchange-rates', component: () => import('@/views/ExchangeRates.vue'), meta: { title: 'FX Rates', titleKey: 'menu.exchange', permission: 'feature:exchange_rates' } },
      { path: 'orders', name: 'orders', component: () => import('@/views/Orders.vue'), meta: { title: 'Orders', titleKey: 'menu.orders', permission: 'feature:orders' } },
      { path: 'pre-orders', name: 'pre-orders', component: () => import('@/views/PreSettlement.vue'), meta: { title: 'Pre-orders', titleKey: 'menu.preOrders', permission: 'feature:pre_orders' } },
      { path: 'refunds', name: 'refunds', component: () => import('@/views/Refunds.vue'), meta: { title: 'Refunds', titleKey: 'menu.refunds', permission: 'feature:refunds' } },
      { path: 'fund-trace', name: 'fund-trace', component: () => import('@/views/FundTrace.vue'), meta: { title: 'Fund Trace', titleKey: 'menu.fundTrace', permission: 'feature:fund_trace' } },
      { path: 'banks', name: 'banks', component: () => import('@/views/Channels.vue'), meta: { title: 'Channels', titleKey: 'menu.banks', permission: 'feature:banks' } },
      { path: 'reconciliation', name: 'reconciliation', component: () => import('@/views/Reconciliation.vue'), meta: { title: 'Reconciliation', titleKey: 'menu.reconciliation', permission: 'feature:reconciliation' } },
      { path: 'fund-transfers', name: 'fund-transfers', component: () => import('@/views/FundTransfers.vue'), meta: { title: 'Transfers', titleKey: 'menu.fundTransfers', permission: 'feature:fund_transfers' } },
      { path: 'reports', name: 'reports', component: () => import('@/views/Reports.vue'), meta: { title: 'Reports', titleKey: 'menu.reports', permission: 'feature:reports' } },
      { path: 'adjustments', name: 'adjustments', component: () => import('@/views/Adjustments.vue'), meta: { title: 'Adjustments', titleKey: 'menu.adjustments', permission: 'feature:adjustments' } },
      { path: 'compliance-overview', redirect: '/sanctions' },
      { path: 'compliance', redirect: '/sanctions' },
      { path: 'sanctions', name: 'sanctions', component: () => import('@/views/Sanctions.vue'), meta: { title: 'Lists', titleKey: 'menu.sanctions', permission: 'feature:sanctions' } },
      { path: 'scans', name: 'scans', component: () => import('@/views/Scans.vue'), meta: { title: 'Screening', titleKey: 'menu.scans', permission: 'feature:scans' } },
      { path: 'system-users', redirect: '/users' },
      { path: 'pre-settlement', redirect: '/pre-orders' },
      { path: 'params', name: 'params', component: () => import('@/views/Params.vue'), meta: { title: 'Parameters', titleKey: 'menu.params', permission: 'feature:params' } },
      { path: 'bank-notifications', name: 'bank-notifications', component: () => import('@/views/BankNotifications.vue'), meta: { title: 'Bank Notifications', titleKey: 'menu.bankNotifications', permission: 'feature:bank_notifications' } },
      { path: 'user-portal', redirect: { path: '/merchants', query: { tab: 'kyc' } } },
      { path: 'agent-extras', redirect: '/agents' },
      { path: 'account-extras', redirect: '/accounts' },
      { path: 'no-access', name: 'no-access', component: () => import('@/views/NoAccess.vue'), meta: { title: 'No access' } }
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFound.vue'), meta: { public: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const needsAuth = to.matched.some((record) => record.meta.requiresAuth)
  if (needsAuth && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return firstAllowedPath(currentUser())
  }
  const permission = to.meta.permission
  if (permission && token && !canAccessPath(currentUser(), permission)) {
    return firstAllowedPath(currentUser())
  }
  return true
})

export default router
