import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import RemittanceApply from '../RemittanceApply.vue'
import { applyRemittance, feePreview, getCustomers } from '@/api/payments'
import { getProfile } from '@/api/auth'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ query: {} })
}))
vi.mock('@/api/payments', () => ({
  applyRemittance: vi.fn(),
  feePreview: vi.fn(),
  getCustomers: vi.fn(),
  sanctionCheck: vi.fn()
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
  'el-radio-group': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div class="funding-group" data-testid="funding-method"><slot /></div>'
  },
  'el-radio': {
    props: ['value', 'label'],
    template: '<div class="funding-radio" :data-value="value || label"><slot /></div>'
  },
  'el-row': passthrough,
  'el-col': passthrough,
  'el-form-item': passthrough,
  'el-select': passthrough,
  'el-option': {
    props: ['label', 'value'],
    template: '<div class="el-option-stub" :data-value="value">{{ label }}</div>'
  },
  'el-input': passthrough,
  'el-button': passthrough,
  'el-form': {
    props: ['disabled'],
    template: '<form class="remittance-form" :data-disabled="String(Boolean(disabled))"><slot /></form>'
  },
  'el-alert': {
    template: '<div class="eligibility-alert"><slot /></div>'
  }
}

const eligibleCustomer = {
  id: 'c-1',
  customer_no: 'C001',
  customer_name: 'Alpha Co',
  legal_name: 'Alpha Co',
  remittance_eligibility: { eligible: true, blockers: [] }
}
const eligibleCustomerB = {
  id: 'c-3',
  customer_no: 'C003',
  customer_name: 'Gamma Co',
  legal_name: 'Gamma Co',
  remittance_eligibility: { eligible: true, blockers: [] }
}
const blockedCustomer = {
  id: 'c-2',
  customer_no: 'C002',
  customer_name: 'Beta Co',
  legal_name: 'Beta Co',
  remittance_eligibility: {
    eligible: false,
    blockers: [{ code: 'SETTLEMENT_ACCOUNT_REQUIRED', message: 'Settlement account missing' }]
  }
}

function mountPage(customerItems = [eligibleCustomer, eligibleCustomerB, blockedCustomer]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = {
    portal_role: 'merchant',
    onboarding_status: 'approved',
    remittance_eligibility: { eligible: true, blockers: [] }
  }
  getProfile.mockResolvedValue(auth.user)
  getCustomers.mockResolvedValue({ items: customerItems })
  return { wrapper: mount(RemittanceApply, {
    global: { plugins: [pinia, i18n], stubs }
  }), auth }
}

describe('merchant remittance with customer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  it('loads customers and keeps submit gated until one is selected', async () => {
    const { wrapper } = mountPage()
    await flushPromises()
    expect(getCustomers).toHaveBeenCalled()
    expect(wrapper.vm.customers).toHaveLength(3)
    expect(wrapper.vm.form.customer_id).toBe('')
    expect(wrapper.vm.formEnabled).toBe(true)
    expect(wrapper.find('.remittance-form').attributes('data-disabled')).toBe('false')
    expect(wrapper.vm.canSubmit).toBe(false)
    expect(feePreview).not.toHaveBeenCalled()
  })

  it('auto-selects when only one eligible customer exists', async () => {
    const { wrapper } = mountPage([eligibleCustomer, blockedCustomer])
    await flushPromises()
    expect(wrapper.vm.form.customer_id).toBe('c-1')
    expect(wrapper.vm.canSubmit).toBe(true)
  })

  it('offers bank and wallet funding methods and submits with customer_id', async () => {
    applyRemittance.mockResolvedValue({ order_no: 'RMT1' })
    const { wrapper } = mountPage([eligibleCustomer])
    await flushPromises()
    expect(wrapper.vm.form.pay_method).toBe('WIRE_TRANSFER')
    expect(wrapper.get('[data-testid="funding-method"]').text()).toContain('Bank')
    expect(wrapper.get('[data-testid="funding-method"]').text()).toContain('Wallet')
    wrapper.vm.form.pay_method = 'WALLET'
    Object.assign(wrapper.vm.form, {
      amount: '100',
      beneficiary_name: 'Supplier',
      beneficiary_account: '001',
      beneficiary_bank: 'Bank'
    })
    wrapper.vm.fee = {
      quote_id: 'RQT1',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    }
    await wrapper.vm.submit()
    expect(applyRemittance.mock.calls[0][0]).toMatchObject({
      quote_id: 'RQT1',
      pay_method: 'WALLET',
      customer_id: 'c-1'
    })
    expect(push).toHaveBeenCalledWith('/orders')
  })

  it('quotes with customer_id when amount is entered', async () => {
    feePreview.mockResolvedValue({
      quote_id: 'RQT-SHA',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    })
    const { wrapper } = mountPage([eligibleCustomer])
    await flushPromises()
    wrapper.vm.form.amount = '1000'
    wrapper.vm.form.fee_bearing = 'SHA'
    await wrapper.vm.preview()
    expect(feePreview).toHaveBeenCalledWith(expect.objectContaining({
      customer_id: 'c-1',
      fee_bearing: 'SHA',
      amount: '1000'
    }))
  })

  it('asks to create a customer only when the list is empty', async () => {
    const { wrapper } = mountPage([])
    await flushPromises()
    expect(wrapper.text()).toContain('Create a customer first')
    expect(wrapper.text()).toContain('Go to Customers')
  })

  it('does not tell the merchant to create a customer when they already have one', async () => {
    const { wrapper } = mountPage([blockedCustomer])
    await flushPromises()
    expect(wrapper.text()).not.toContain('Create a customer first')
    expect(wrapper.text()).toContain('Settlement account missing')
  })
})
