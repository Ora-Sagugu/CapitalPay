import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentMerchant from '../AgentMerchant.vue'
import { getAgentKycList, getAgentMerchants } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  getAgentKycList: vi.fn(),
  getAgentKycDetail: vi.fn(),
  reviewAgentKyc: vi.fn(),
  getAgentMerchants: vi.fn()
}))

vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'agent' }
  return mount(AgentMerchant, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('agent merchant page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getAgentKycList.mockResolvedValue({
      items: [
        {
          id: 'u1',
          username: 'newshop',
          legal_person: 'New Shop Ltd',
          email: 'newshop@example.com',
          agent_review_status: 'pending'
        }
      ],
      total: 1,
      stats: { pending_profile: 1, approved: 0, rejected: 0 }
    })
    getAgentMerchants.mockResolvedValue({
      items: [
        {
          id: 'm1',
          merchant_name: 'Agreed Trade Ltd',
          contact_email: 'ada@example.com',
          customer_count: 3
        }
      ]
    })
  })

  it('lists pending applications and agreed merchants', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Merchant')
    expect(wrapper.text()).toContain('Pending merchants')
    expect(wrapper.text()).toContain('New Shop Ltd')
    expect(wrapper.text()).toContain('newshop@example.com')
    expect(wrapper.text()).toContain('Approve')
    expect(wrapper.text()).toContain('Reject')
    expect(wrapper.text()).not.toContain('Customer no.')
    expect(wrapper.text()).not.toContain('Legal Person')
    expect(wrapper.text()).not.toContain('ID Type')
    expect(wrapper.text()).not.toContain('Review Status')
    expect(wrapper.text()).not.toContain('Submission Time')
    expect(wrapper.text()).toContain('Agreed merchants')
    expect(wrapper.text()).toContain('Agreed Trade Ltd')
    expect(wrapper.text()).toContain('ada@example.com')
    expect(wrapper.text()).toContain('3')
    expect(getAgentKycList).toHaveBeenCalled()
    expect(getAgentMerchants).toHaveBeenCalled()
  })
})
