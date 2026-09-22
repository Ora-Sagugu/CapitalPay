import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import Overview from '../Overview.vue'
import { getRemittanceStats } from '@/api/payments'

vi.mock('@/api/payments', () => ({
  getRemittanceStats: vi.fn()
}))

function mountPage() {
  return mount(Overview, {
    global: {
      plugins: [i18n, ElementPlus]
    }
  })
}

describe('merchant overview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18n.global.locale.value = 'en-US'
    getRemittanceStats.mockResolvedValue({
      period: 'month',
      remittance_count: 4,
      success_count: 3,
      success_rate: '75.00',
      by_currency: [
        { currency: 'USD', total_amount: '400.00', total_fee: '20.00', order_count: 4 }
      ]
    })
  })

  it('loads KPIs for the selected period', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(getRemittanceStats).toHaveBeenCalledWith({ period: 'month' })
    expect(wrapper.get('[data-testid="kpi-count"]').text()).toContain('4')
    expect(wrapper.get('[data-testid="kpi-amount"]').text()).toContain('400.00')
    expect(wrapper.get('[data-testid="kpi-amount"]').text()).toContain('USD')
    expect(wrapper.get('[data-testid="kpi-success"]').text()).toContain('75.00%')
    expect(wrapper.get('[data-testid="kpi-fee"]').text()).toContain('20.00')
  })
})
