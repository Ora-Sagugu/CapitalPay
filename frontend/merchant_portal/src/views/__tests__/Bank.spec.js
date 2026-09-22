import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import Bank from '../Bank.vue'
import { getAccountLedger, listBoundAccounts, listSupportedChannels } from '@/api/payments'

vi.mock('@/api/payments', () => ({
  listBoundAccounts: vi.fn(),
  getAccountLedger: vi.fn(),
  listSupportedChannels: vi.fn()
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
  auth.user = { onboarding_status: 'approved', portal_role: 'merchant' }
  return mount(Bank, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('customer bank page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    listBoundAccounts.mockResolvedValue({
      registration: {
        id: 'reg-1',
        source: 'registration',
        bank_name: 'Equity Bank',
        account_holder: 'Horizon Trade Limited',
        account_number: '****0011',
        swift_code: 'EQBLKENA',
        status: 'ACTIVE',
        currency: 'USD',
        balance: '10000.00',
        balances: [{ currency: 'USD', balance: '10000.00' }]
      },
      added_cards: [],
      balances: [{ currency: 'USD', balance: '10000.00', status: 'ACTIVE' }]
    })
    getAccountLedger.mockResolvedValue({
      items: [
        {
          id: 'e1',
          currency: 'USD',
          entry_type: 'CREDIT',
          amount: '10000.00',
          balance_after: '10000.00',
          order_no: 'RMT1',
          remark: 'Collection confirmed',
          created_at: '2026-09-11T04:00:00Z'
        }
      ],
      total: 1
    })
    listSupportedChannels.mockResolvedValue({
      items: [
        { bank_name: 'Bank of China', country: 'China' },
        { bank_name: 'HSBC Holdings', country: 'United Kingdom' }
      ]
    })
  })

  it('renders bank details, book balances, ledger and channels', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Bank')
    expect(wrapper.text()).toContain('system book')
    expect(wrapper.text()).toContain('not initiated')
    expect(wrapper.text()).toContain('Equity Bank')
    expect(wrapper.text()).toContain('****0011')
    expect(wrapper.text()).toContain('Horizon Trade Limited')
    expect(wrapper.text()).toContain('EQBLKENA')
    expect(wrapper.text()).toContain('USD')
    expect(wrapper.text()).toContain('10,000.00')
    expect(wrapper.text()).toContain('RMT1')
    expect(wrapper.text()).toContain('Credit')
    expect(wrapper.text()).toContain('Channels')
    expect(wrapper.text()).toContain('Bank Name')
    expect(wrapper.text()).toContain('Country')
    expect(wrapper.text()).toContain('Bank of China')
    expect(wrapper.text()).toContain('China')
    expect(wrapper.text()).toContain('HSBC Holdings')
    expect(wrapper.text()).toContain('United Kingdom')
    expect(listBoundAccounts).toHaveBeenCalled()
    expect(getAccountLedger).toHaveBeenCalled()
    expect(listSupportedChannels).toHaveBeenCalled()
  })
})
