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
  auth.user = { onboarding_status: 'approved', portal_role: 'merchant' }
  return mount(Accounts, {
    global: {
      plugins: [pinia, i18n, ElementPlus],
      stubs: {
        RouterLink: { template: '<a class="router-link-stub"><slot /></a>' }
      }
    }
  })
}

describe('customer accounts hub', () => {
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

  it('renders bank, wallet and cards rails and hides bank account details', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Accounts')
    expect(wrapper.get('[data-testid="rail-bank"]').text()).toContain('CapitalPay')
    expect(wrapper.get('[data-testid="rail-wallet"]').text()).toContain('Wallet')
    expect(wrapper.get('[data-testid="rail-cards"]').text()).toContain('Cards')
    expect(wrapper.find('[data-testid="rail-qr"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Equity Bank')
    expect(wrapper.text()).not.toContain('****0011')
    expect(wrapper.text()).not.toContain('Horizon Trade Limited')
    expect(wrapper.text()).not.toContain('Your CapitalPay account')
    expect(wrapper.text()).not.toContain('combined total')
    expect(listBoundAccounts).toHaveBeenCalled()
    expect(getAccountLedger).toHaveBeenCalled()
  })

  it('totals CapitalPay deposit, wallet and card balances', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const { useFundingStore } = await import('@/store/funding')
    const funding = useFundingStore()
    funding.wallets = [{ currency: 'USD', balance: '200.00', available: '200.00', frozen: '0', status: 'ACTIVE' }]
    funding.cards = [{ currency: 'USD', balance: '50.00', available: '50.00', frozen: '0', status: 'ACTIVE' }]
    await flushPromises()
    const total = wrapper.get('[data-testid="spendable"]').text()
    expect(total).toContain('Total')
    expect(total).toContain('10,250.00')
    expect(wrapper.find('[data-testid="card-receivables"]').exists()).toBe(false)
  })

  it('includes card available balances in the spendable total', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const { useFundingStore } = await import('@/store/funding')
    const funding = useFundingStore()
    funding.wallets = [{ currency: 'USD', available: '200.00', status: 'ACTIVE' }]
    funding.cards = [{
      currency: 'USD',
      available: '50.00',
      pending: '10.00',
      reserved: '20.00',
      dispute_hold: '30.00',
      ledger: '110.00',
      status: 'ACTIVE'
    }]
    await flushPromises()
    expect(wrapper.get('[data-testid="spendable"]').text()).toContain('10,250.00')
  })
})
