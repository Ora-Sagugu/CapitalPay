import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentAccount from '../AgentAccount.vue'
import { getAgentEarnings } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  getAgentEarnings: vi.fn()
}))
vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

async function mountPage(path = '/agent/account') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'agent' }
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/agent/account', name: 'agent-account', component: AgentAccount }
    ]
  })
  await router.push(path)
  await router.isReady()
  return mount(AgentAccount, {
    global: { plugins: [pinia, i18n, ElementPlus, router] }
  })
}

describe('agent account', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getAgentEarnings.mockResolvedValue({ items: [], total: 0, summary: [], by_customer: [] })
  })

  it('shows earnings only without the CURRENT module', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Account')
    expect(wrapper.text()).not.toContain('CURRENT')
    expect(wrapper.text()).toContain('Total Agent Fee')
    expect(getAgentEarnings).toHaveBeenCalled()
  })
})
