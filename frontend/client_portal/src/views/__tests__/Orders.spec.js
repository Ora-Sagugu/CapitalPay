import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import Orders from '../Orders.vue'
import { getOrders } from '@/api/orders'
import { getOrderStats } from '@/api/dashboard'

vi.mock('@/api/orders', () => ({
  getOrders: vi.fn(),
  getOrderDetail: vi.fn(),
  getOrderSanctionReview: vi.fn(),
  reviewOrder: vi.fn(),
  confirmPayment: vi.fn(),
  confirmTransfer: vi.fn(),
  getPayoutBanks: vi.fn(),
  initiateOrderRefund: vi.fn()
}))
vi.mock('@/api/dashboard', () => ({
  getOrderStats: vi.fn()
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: () => true
  })
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  PageHeader: passthrough,
  KpiCards: passthrough,
  StatusPill: { props: ['value'], template: '<span>{{ value }}</span>' },
  EmptyState: passthrough,
  'el-select': passthrough,
  'el-option': passthrough,
  'el-input': passthrough,
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-table': { props: ['data'], template: '<div class="table"><slot /></div>' },
  'el-table-column': { template: '<div></div>' },
  'el-pagination': passthrough,
  'el-drawer': { template: '<div class="drawer"><slot /></div>' },
  'el-descriptions': passthrough,
  'el-descriptions-item': passthrough,
  'el-timeline': passthrough,
  'el-timeline-item': passthrough,
  'el-dialog': { template: '<div class="dialog"><slot /><slot name="footer" /></div>' },
  'el-radio-group': passthrough,
  'el-radio': passthrough,
  'el-empty': passthrough,
  'el-tag': passthrough,
  'el-collapse': passthrough,
  'el-collapse-item': passthrough
}

function mountPage() {
  return mount(Orders, { global: { plugins: [i18n], stubs } })
}

describe('ops orders confirm transfer gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18n.global.locale.value = 'en-US'
    getOrderStats.mockResolvedValue({})
    getOrders.mockResolvedValue({
      results: [
        {
          order_no: 'RMT_PENDING_AGENT',
          status: 'PAY_RECEIVED',
          agent_payout_request_status: 'pending'
        }
      ],
      count: 1
    })
  })

  it('blocks Confirm transfer until the agent requests payout', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'pending'
    })).toBe(false)
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'requested'
    })).toBe(true)
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PENDING_PAY',
      agent_payout_request_status: 'none'
    })).toBe(true)
    expect(wrapper.vm.canConfirmTransfer({
      status: 'PENDING_PAY',
      agent_payout_request_status: 'pending'
    })).toBe(false)
    expect(wrapper.vm.isAwaitingAgentPayout({
      status: 'PAY_RECEIVED',
      agent_payout_request_status: 'pending'
    })).toBe(true)
  })
})
