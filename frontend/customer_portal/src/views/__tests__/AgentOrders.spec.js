import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentOrders from '../AgentOrders.vue'
import { getAgentOrders } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  getAgentOrders: vi.fn(),
  getAgentOrderDetail: vi.fn(),
  reviewAgentOrder: vi.fn(),
  requestAgentPayout: vi.fn()
}))
vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  'el-alert': passthrough,
  'el-input': passthrough,
  'el-select': passthrough,
  'el-option': passthrough,
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-table': {
    props: ['data'],
    template: '<div class="table"><slot /></div>'
  },
  'el-table-column': { template: '<div></div>' },
  'el-empty': passthrough,
  'el-pagination': passthrough,
  'el-drawer': { template: '<div class="drawer"><slot /></div>' },
  'el-descriptions': passthrough,
  'el-descriptions-item': passthrough,
  'el-tag': passthrough
}

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'agent' }
  return mount(AgentOrders, {
    global: { plugins: [pinia, i18n], stubs }
  })
}

describe('agent orders payout request', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getAgentOrders.mockResolvedValue({
      items: [
        {
          order_no: 'RMT_AWAIT',
          status: 'PAY_RECEIVED',
          agent_payout_request_status: 'pending',
          amount: '12.00'
        },
        {
          order_no: 'RMT_REVIEW',
          status: 'PENDING_AGENT_REVIEW',
          agent_payout_request_status: 'none',
          amount: '8.00'
        }
      ],
      total: 2,
      stats: { total: 2, pending: 1, awaiting_payout: 1, agreed: 0, rejected: 0 }
    })
  })

  it('offers Request payout only after funds are received and pending', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.vm.canRequestPayout({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'pending'
    })).toBe(true)
    expect(wrapper.vm.canRequestPayout({
      status: 'PENDING_PAY',
      agent_payout_request_status: 'none'
    })).toBe(false)
    expect(wrapper.vm.canRequestPayout({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'requested'
    })).toBe(false)
    expect(wrapper.text()).toContain('Awaiting payout')
  })
})
