import { createRouter, createWebHistory } from 'vue-router'

import {
  defaultHomePath,
  defaultLoginRouteName,
  isAgentApp,
  otherPortalUrl
} from '@/config/portal'

const CUSTOMER_ONLY = new Set(['accounts', 'orders', 'remittance', 'wallet'])
const AGENT_ONLY = new Set(['agent-overview', 'agent-kyc', 'agent-orders', 'agent-remittance', 'agent-customers', 'agent-account', 'agent-earnings', 'agent-transfers'])
const LOGIN_ROUTES = new Set(['login', 'agent-login'])

const homePath = defaultHomePath()

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/agent/login',
    name: 'agent-login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, portalRole: 'agent' }
  },
  {
    path: '/pay/:orderNo',
    name: 'cashier',
    component: () => import('@/views/CashierPay.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layout/DefaultLayout.vue'),
    redirect: homePath,
    meta: { requiresAuth: true },
    children: [
      { path: 'onboarding', name: 'onboarding', component: () => import('@/views/OnboardingWizard.vue'), meta: { title: 'Onboarding' } },
      { path: 'remittance', name: 'remittance', component: () => import('@/views/RemittanceApply.vue'), meta: { title: 'Remittance' } },
      { path: 'orders', name: 'orders', component: () => import('@/views/Orders.vue'), meta: { title: 'Orders' } },
      { path: 'accounts', name: 'accounts', component: () => import('@/views/Accounts.vue'), meta: { title: 'Accounts' } },
      { path: 'wallet', name: 'wallet', component: () => import('@/views/Wallet.vue'), meta: { title: 'Wallet' } },
      { path: 'agent', name: 'agent-overview', component: () => import('@/views/AgentOverview.vue'), meta: { title: 'Agent' } },
      { path: 'agent/kyc', name: 'agent-kyc', component: () => import('@/views/AgentKyc.vue'), meta: { title: 'KYC' } },
      { path: 'agent/orders', name: 'agent-orders', component: () => import('@/views/AgentOrders.vue'), meta: { title: 'Orders' } },
      { path: 'agent/remittance', name: 'agent-remittance', component: () => import('@/views/AgentRemittance.vue'), meta: { title: 'Remittance' } },
      { path: 'agent/customers', name: 'agent-customers', component: () => import('@/views/AgentCustomers.vue'), meta: { title: 'Customers' } },
      { path: 'agent/account', name: 'agent-account', component: () => import('@/views/AgentAccount.vue'), meta: { title: 'Account' } },
      { path: 'agent/earnings', name: 'agent-earnings', component: () => import('@/views/AgentEarnings.vue'), meta: { title: 'Earnings' } },
      { path: 'agent/transfers', name: 'agent-transfers', component: () => import('@/views/AgentTransfers.vue'), meta: { title: 'Transfers' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: homePath }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

function readPortalRole() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return user?.portal_role || 'none'
  } catch {
    return 'none'
  }
}

function homeForRole(role) {
  if (role === 'agent') return { name: 'agent-overview' }
  return { name: 'accounts' }
}

function isAgentDestination(to) {
  return AGENT_ONLY.has(to.name) || (to.path || '').startsWith('/agent')
}

function assignOtherPortal(to) {
  const url = otherPortalUrl()
  if (!url) return false
  const target = new URL(url, window.location.origin)
  if (to.fullPath && to.fullPath !== '/agent/login') {
    target.searchParams.set('redirect', to.fullPath)
  }
  window.location.assign(target.toString())
  return true
}

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!isAgentApp()) {
    if (to.name === 'agent-login' || (!token && to.meta.public !== true && isAgentDestination(to))) {
      if (assignOtherPortal(to)) return false
    }
  }
  if (isAgentApp() && to.name === 'agent-login') {
    return { name: 'login', query: to.query, hash: to.hash }
  }
  if (to.meta.public) {
    if (token && LOGIN_ROUTES.has(to.name)) {
      return homeForRole(readPortalRole())
    }
    return true
  }
  if (to.meta.requiresAuth && !token) {
    return {
      name: defaultLoginRouteName(),
      query: { redirect: to.fullPath }
    }
  }
  const role = readPortalRole()
  if (role === 'agent' && CUSTOMER_ONLY.has(to.name)) {
    return { name: 'agent-overview' }
  }
  if (role === 'customer' && AGENT_ONLY.has(to.name)) {
    return { name: 'accounts' }
  }
  return true
})

export default router
