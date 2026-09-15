import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import Reports from '../Reports.vue'
import { getAgents } from '@/api/agents'
import { getMerchants } from '@/api/merchants'
import {
  getAnalyticsSummary, getAnalyticsTrend, getAnalyticsBreakdowns,
  getAnalyticsTransactions, getAnalyticsTrace
} from '@/api/report'

vi.mock('echarts', () => ({
  init: () => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })
}))
vi.mock('@/api/agents', () => ({ getAgents: vi.fn() }))
vi.mock('@/api/merchants', () => ({ getMerchants: vi.fn() }))
vi.mock('@/api/report', () => ({
  queryReport: vi.fn(),
  exportReport: vi.fn(),
  generateReport: vi.fn(),
  getAnalyticsSummary: vi.fn(),
  getAnalyticsTrend: vi.fn(),
  getAnalyticsBreakdowns: vi.fn(),
  getAnalyticsTransactions: vi.fn(),
  getAnalyticsTrace: vi.fn(),
  exportAnalytics: vi.fn()
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: (code) => code === 'feature:reports'
  })
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  PageHeader: passthrough,
  EmptyState: { props: ['message'], template: '<div class="empty">{{ message }}</div>' },
  StatusPill: { props: ['value'], template: '<span>{{ value }}</span>' },
  'el-alert': passthrough,
  'el-date-picker': passthrough,
  'el-select': passthrough,
  'el-option': passthrough,
  'el-input': passthrough,
  'el-button': { template: '<button v-bind="$attrs"><slot /></button>' },
  'el-tabs': { template: '<div><slot /></div>' },
  'el-tab-pane': { template: '<div><slot /></div>' },
  'el-table': { props: ['data'], template: '<div class="table"><slot /></div>' },
  'el-table-column': passthrough,
  'el-pagination': passthrough,
  'el-drawer': { template: '<div class="drawer"><slot /></div>' },
  'el-timeline': passthrough,
  'el-timeline-item': passthrough,
  'el-tag': passthrough
}

function mountPage() {
  return mount(Reports, { global: { plugins: [i18n], stubs } })
}

describe('internal analytics reports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18n.global.locale.value = 'en-US'
    getAgents.mockResolvedValue({ results: [{ id: 'a1', agent_name: 'Agent A' }] })
    getMerchants.mockResolvedValue({ results: [{ id: 'm1', merchant_name: 'Merchant M' }] })
    getAnalyticsSummary.mockResolvedValue({
      application: { count: 2, by_currency: [{ currency: 'USD', amount: '100.00', count: 1 }, { currency: 'KES', amount: '200.00', count: 1 }] },
      confirmed_collection: { count: 1, by_currency: [{ currency: 'USD', amount: '100.00', count: 1 }] },
      successful_refunds: { count: 0, by_currency: [] },
      pending: { review: { count: 1 }, pay: { count: 0 }, settle: { count: 0 } },
      funnel: [{ code: 'applied', label: 'Application', count: 2 }],
      fee_share_estimated: { by_currency: [] },
      coverage: { user_id: { rate: '0.5000' } }
    })
    getAnalyticsTrend.mockResolvedValue({
      series: [{ date: '08-30', application_count: 2, by_currency: [{ currency: 'USD', application_amount: '100.00' }] }]
    })
    getAnalyticsBreakdowns.mockResolvedValue({
      coverage: { rate: '0.5000' },
      rows: [{ key: 'm1', label: 'Merchant M', count: 2, unlinked: false, by_currency: [{ currency: 'USD', amount: '100.00' }] }]
    })
    getAnalyticsTransactions.mockResolvedValue({
      count: 1,
      results: [{
        order_no: 'P001', merchant_name: 'Merchant M', user_id: '', user_linked: false,
        from_currency: 'USD', amount: '100.00', fee_amount: '1.00', status: 'PENDING_REVIEW',
        beneficiary_account: '****6789'
      }]
    })
    getAnalyticsTrace.mockResolvedValue({
      timeline: [{ code: 'payout', title: 'Correspondent payout', verified: false, at: '' }],
      money_movements: []
    })
  })

  it('loads overview KPIs split by currency', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(getAnalyticsSummary).toHaveBeenCalled()
    expect(wrapper.find('[data-test="kpi-grid"]').text()).toContain('USD')
    expect(wrapper.find('[data-test="kpi-grid"]').text()).toContain('KES')
    expect(wrapper.find('[data-test="kpi-grid"]').text()).toContain('Confirmed collection')
  })

  it('renders empty state when there are no transactions', async () => {
    getAnalyticsTransactions.mockResolvedValue({ count: 0, results: [] })
    const wrapper = mountPage()
    await flushPromises()
    wrapper.vm.tab = 'transactions'
    await wrapper.vm.loadTransactions()
    await flushPromises()
    expect(wrapper.text()).toContain('No records')
  })

  it('opens unverified fund timeline from a transaction', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await wrapper.vm.openTrace('P001')
    await flushPromises()
    expect(getAnalyticsTrace).toHaveBeenCalledWith('P001')
    expect(wrapper.find('[data-test="trace-drawer"]').text()).toContain('Unverified')
  })
})
