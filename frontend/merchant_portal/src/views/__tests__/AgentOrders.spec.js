import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentOrders from '../AgentOrders.vue'
import { getAgentOrders } from '@/api/agent'

vi.mock('@/api/agent', () => ({
  getAgentOrders: vi.fn(),
  getAgentOrderDetail: vi.fn()
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

describe('agent orders', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getAgentOrders.mockResolvedValue({
      items: [
        {
          order_no: 'RMT_REVIEW',
          status: 'PENDING_REVIEW',
          merchant_name: 'Horizon Trade Limited',
          amount: '12.00',
          agent_fee: '1.50'
        }
      ],
      total: 1,
      stats: { total: 1, pending: 1, awaiting_payout: 0, agreed: 0, rejected: 0 }
    })
  })

  it('lists agent-booked remittances awaiting operations review', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(getAgentOrders).toHaveBeenCalled()
    expect(wrapper.vm.rows).toHaveLength(1)
    expect(wrapper.vm.rows[0].order_no).toBe('RMT_REVIEW')
    expect(wrapper.vm.canRequestPayout).toBeUndefined()
    expect(wrapper.text()).not.toContain('Awaiting payout')
    expect(wrapper.text()).not.toContain('Request payout')
  })

  it('is view-only for merchant remittances', async () => {
    getAgentOrders.mockResolvedValue({
      items: [
        {
          order_no: 'RMT_MERCHANT',
          status: 'PENDING_REVIEW',
          merchant_name: 'Horizon Trade Limited',
          amount: '500.00',
          read_only: true
        }
      ],
      total: 1,
      stats: { total: 1, pending: 1, awaiting_payout: 0, agreed: 0, rejected: 0 }
    })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.vm.rows[0].read_only).toBe(true)
    expect(wrapper.text()).toContain('read-only')
    expect(wrapper.text()).not.toContain('Request payout')
    expect(wrapper.html()).not.toContain('ordersAgree')
    expect(wrapper.html()).not.toContain('ordersReject')
  })

  it('labels the fee column as Agent Fee', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(i18n.global.t('agent.ordersAgentFee')).toBe('Agent Fee')
    expect(wrapper.vm.formatAgentFee('1.50')).toBe('1.50')
    expect(wrapper.vm.formatAgentFee(null)).toBe('—')
  })
})
