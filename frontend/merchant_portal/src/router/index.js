import { createRouter, createWebHistory } from 'vue-router'

import { ENABLE_CARDS } from '@/config/features'
import {
  defaultHomePath,
  defaultLoginRouteName,
  isAgentApp,
  otherPortalUrl
} from '@/config/portal'

const MERCHANT_ONLY = new Set(['overview', 'profile', 'accounts', 'orders', 'remittance', 'customers', 'bank', 'wallet', 'cards'])
const AGENT_ONLY = new Set(['agent-overview', 'agent-kyc', 'agent-orders', 'agent-account', 'agent-merchant', 'agent-customers'])
const LOGIN_ROUTES = new Set(['login', 'agent-login'])
// Bank / Wallet / Cards are Merchant funding rails (not shown on Agent).

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
      { path: 'overview', name: 'overview', component: () => import('@/views/Overview.vue'), meta: { title: 'Overview' } },
      { path: 'profile', name: 'profile', component: () => import('@/views/Profile.vue'), meta: { title: 'Profile' } },
      { path: 'customers', name: 'customers', component: () => import('@/views/Customers.vue'), meta: { title: 'Customers' } },
      { path: 'remittance', name: 'remittance', component: () => import('@/views/RemittanceApply.vue'), meta: { title: 'Remittance' } },
      { path: 'orders', name: 'orders', component: () => import('@/views/Orders.vue'), meta: { title: 'Orders' } },
      { path: 'accounts', name: 'accounts', component: () => import('@/views/Accounts.vue'), meta: { title: 'Accounts' } },
      { path: 'bank', name: 'bank', component: () => import('@/views/Bank.vue'), meta: { title: 'Bank' } },
      { path: 'wallet', name: 'wallet', component: () => import('@/views/Wallet.vue'), meta: { title: 'Wallet' } },
      { path: 'cards', name: 'cards', component: () => import('@/views/Cards.vue'), meta: { title: 'Cards' } },
      { path: 'agent', name: 'agent-overview', component: () => import('@/views/AgentOverview.vue'), meta: { title: 'Agent' } },
      { path: 'agent/customers', name: 'agent-customers', component: () => import('@/views/AgentCustomers.vue'), meta: { title: 'Customers' } },
      { path: 'agent/kyc', name: 'agent-kyc', redirect: { name: 'agent-merchant' } },
      { path: 'agent/orders', name: 'agent-orders', component: () => import('@/views/AgentOrders.vue'), meta: { title: 'Orders' } },
      { path: 'agent/account', name: 'agent-account', component: () => import('@/views/AgentAccount.vue'), meta: { title: 'Account' } },
      { path: 'agent/merchant', name: 'agent-merchant', component: () => import('@/views/AgentMerchant.vue'), meta: { title: 'Merchant' } },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: homePath }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

function readPortalRole() {
  return readStoredUser()?.portal_role || 'none'
}

function homeForUser() {
  const user = readStoredUser()
  const role = user?.portal_role || 'none'
  const status = user?.onboarding_status || 'none'
  if (status !== 'approved') return { name: 'onboarding' }
  if (role === 'agent') return { name: 'agent-overview' }
  return { name: 'overview' }
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
      return homeForUser()
    }
    return true
  }
  if (to.meta.requiresAuth && !token) {
    return {
      name: defaultLoginRouteName(),
      query: { redirect: to.fullPath }
    }
  }
  const status = readStoredUser()?.onboarding_status || 'none'
  if (status !== 'approved' && to.name !== 'onboarding') {
    return { name: 'onboarding' }
  }
  if (status === 'approved' && to.name === 'onboarding') {
    return homeForUser()
  }
  if (!ENABLE_CARDS && to.name === 'cards') {
    return homeForUser()
  }
  const role = readPortalRole()
  if (role === 'agent' && MERCHANT_ONLY.has(to.name)) {
    return { name: 'agent-overview' }
  }
  if (role === 'merchant' && AGENT_ONLY.has(to.name)) {
    return { name: 'overview' }
  }
  return true
})

export default router
