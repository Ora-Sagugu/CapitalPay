import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import Accounts from '../Accounts.vue'
import { getAccountLedger, listBoundAccounts } from '@/api/payments'

vi.mock('@/api/payments', () => ({
  listBoundAccounts: vi.fn(),
  getAccountLedger: vi.fn()
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
  auth.user = { onboarding_status: 'approved', portal_role: 'customer' }
  return mount(Accounts, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('customer accounts page', () => {
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
  })

  it('renders account balances and ledger without bank account details', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Accounts')
    expect(wrapper.text()).toContain('Available balances after funds are received')
    expect(wrapper.text()).not.toContain('Virtual Accounts')
    expect(wrapper.text()).not.toContain('Account details')
    expect(wrapper.text()).not.toContain('Equity Bank')
    expect(wrapper.text()).not.toContain('****0011')
    expect(wrapper.text()).not.toContain('Horizon Trade Limited')
    expect(wrapper.text()).toContain('USD')
    expect(wrapper.text()).toContain('10,000.00')
    expect(wrapper.text()).toContain('RMT1')
    expect(wrapper.text()).toContain('Credit')
    expect(listBoundAccounts).toHaveBeenCalled()
    expect(getAccountLedger).toHaveBeenCalled()
  })
})
