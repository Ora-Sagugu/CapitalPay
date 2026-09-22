import { beforeEach, describe, expect, it } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

import { ENABLE_CARDS } from '@/config/features'

/**
 * Mirrors the role guard in src/router/index.js:
 * bank / wallet / cards are merchant-only; agent routes stay agent-only.
 */
function buildGuardRouter() {
  const MERCHANT_ONLY = new Set(['overview', 'profile', 'accounts', 'orders', 'remittance', 'customers', 'bank', 'wallet', 'cards'])
  const AGENT_ONLY = new Set(['agent-overview', 'agent-account'])

  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/overview', name: 'overview', component: { template: '<div />' } },
      { path: '/profile', name: 'profile', component: { template: '<div />' } },
      { path: '/accounts', name: 'accounts', component: { template: '<div />' } },
      { path: '/bank', name: 'bank', component: { template: '<div />' } },
      { path: '/wallet', name: 'wallet', component: { template: '<div />' } },
      { path: '/cards', name: 'cards', component: { template: '<div />' } },
      { path: '/agent', name: 'agent-overview', component: { template: '<div />' } },
      { path: '/agent/account', name: 'agent-account', component: { template: '<div />' } }
    ]
  })

  router.beforeEach((to) => {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    const role = user?.portal_role || 'none'
    if (!ENABLE_CARDS && to.name === 'cards') {
      return role === 'agent' ? { name: 'agent-overview' } : { name: 'overview' }
    }
    if (role === 'agent' && MERCHANT_ONLY.has(to.name)) return { name: 'agent-overview' }
    if (role === 'merchant' && AGENT_ONLY.has(to.name)) return { name: 'overview' }
    return true
  })
  return router
}

describe('merchant funding rail routes', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('blocks agents from bank and wallet', async () => {
    localStorage.setItem('user', JSON.stringify({ portal_role: 'agent', onboarding_status: 'approved' }))
    const router = buildGuardRouter()
    await router.push('/bank')
    expect(router.currentRoute.value.name).toBe('agent-overview')
    await router.push('/wallet')
    expect(router.currentRoute.value.name).toBe('agent-overview')
  })

  it('lets merchants open bank and wallet', async () => {
    localStorage.setItem('user', JSON.stringify({ portal_role: 'merchant', onboarding_status: 'approved' }))
    const router = buildGuardRouter()
    await router.push('/bank')
    expect(router.currentRoute.value.name).toBe('bank')
    await router.push('/wallet')
    expect(router.currentRoute.value.name).toBe('wallet')
  })

  it('redirects agents away from cards (merchant-only rail)', async () => {
    localStorage.setItem('user', JSON.stringify({ portal_role: 'agent', onboarding_status: 'approved' }))
    const router = buildGuardRouter()
    await router.push('/cards')
    expect(router.currentRoute.value.name).toBe('agent-overview')
  })

  it('lets merchants open cards when the feature is enabled', async () => {
    if (!ENABLE_CARDS) return
    localStorage.setItem('user', JSON.stringify({ portal_role: 'merchant', onboarding_status: 'approved' }))
    const router = buildGuardRouter()
    await router.push('/cards')
    expect(router.currentRoute.value.name).toBe('cards')
  })

  it('still blocks agents from merchant-only profile/accounts', async () => {
    localStorage.setItem('user', JSON.stringify({ portal_role: 'agent', onboarding_status: 'approved' }))
    const router = buildGuardRouter()
    await router.push('/profile')
    expect(router.currentRoute.value.name).toBe('agent-overview')
    await router.push('/accounts')
    expect(router.currentRoute.value.name).toBe('agent-overview')
  })
})
