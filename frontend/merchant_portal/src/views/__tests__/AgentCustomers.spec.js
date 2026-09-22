import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentCustomers from '../AgentCustomers.vue'
import { getAgentCustomers } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  getAgentCustomers: vi.fn()
}))

vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

const stubs = {
  'el-alert': true,
  'el-input': true,
  'el-button': { template: '<button @click="$attrs.onClick"><slot /></button>' },
  'el-table': {
    props: ['data'],
    template: '<div class="table"><div v-for="row in data" :key="row.id" class="row">{{ row.legal_name }} / {{ row.merchant_name }}</div><slot /></div>'
  },
  'el-table-column': true,
  'el-tag': { template: '<span><slot /></span>' },
  'el-empty': { props: ['description'], template: '<div class="empty">{{ description }}</div>' },
  'el-drawer': { template: '<div class="drawer"><slot /></div>' },
  'el-descriptions': true,
  'el-descriptions-item': true
}

describe('agent customers (read-only)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    setActivePinia(createPinia())
  })

  it('lists customers of bound merchants without create actions', async () => {
    const auth = useAuthStore()
    auth.token = 'token'
    auth.user = { onboarding_status: 'approved', portal_role: 'agent' }
    getAgentCustomers.mockResolvedValue({
      items: [
        {
          id: '1',
          customer_no: 'AC001',
          legal_name: 'Buyer One',
          merchant_no: 'M001',
          merchant_name: 'Lagos Imports Ltd',
          contact_email: 'buyer@example.com',
          id_type: 'passport',
          id_number: 'P123',
          nationality: 'KE',
          kyc_status: 'approved'
        }
      ]
    })
    const wrapper = mount(AgentCustomers, {
      global: { plugins: [i18n], stubs }
    })
    await flushPromises()
    expect(getAgentCustomers).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Customers')
    expect(wrapper.text()).toContain('View only')
    expect(wrapper.text()).toContain('Buyer One')
    expect(wrapper.text()).toContain('Lagos Imports Ltd')
    expect(wrapper.text()).not.toContain('New customer')
    expect(wrapper.text()).not.toContain('Submit KYC')
    expect(wrapper.find('.empty').exists()).toBe(false)
  })
})
