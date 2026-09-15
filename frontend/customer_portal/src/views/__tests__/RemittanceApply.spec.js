import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import RemittanceApply from '../RemittanceApply.vue'
import { applyRemittance, feePreview } from '@/api/payments'
import { getProfile } from '@/api/auth'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))
vi.mock('@/api/payments', () => ({
  applyRemittance: vi.fn(),
  feePreview: vi.fn()
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

function profile(eligible, code = '') {
  return {
    onboarding_status: 'approved',
    merchant_status: eligible ? 'ACTIVE' : 'PENDING',
    activation_stage: eligible ? 'ACTIVE' : 'KYC_PENDING',
    remittance_eligibility: {
      eligible,
      blockers: eligible ? [] : [{
        code,
        message: 'Initial review has been completed. KYC remains pending.'
      }]
    }
  }
}

function mountPage(currentProfile) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = currentProfile
  getProfile.mockResolvedValue(currentProfile)
  return { wrapper: mount(RemittanceApply, {
    global: { plugins: [pinia, i18n], stubs }
  }), auth }
}

describe('customer remittance application', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  it('gates a KYC-pending merchant before quote or submit', async () => {
    const { wrapper } = mountPage(profile(false, 'MERCHANT_PENDING'))
    await flushPromises()
    expect(wrapper.find('.eligibility-alert').text()).toContain('KYC')
    expect(wrapper.find('.remittance-form').attributes('data-disabled')).toBe('true')
    expect(feePreview).not.toHaveBeenCalled()
  })

  it('clears an old quote as soon as a financial input changes', async () => {
    const { wrapper } = mountPage(profile(true))
    await flushPromises()
    wrapper.vm.fee = {
      quote_id: 'OLD',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    }
    wrapper.vm.invalidateQuote()
    expect(wrapper.vm.fee).toBeNull()
  })

  it('submits one request with quote id and a stable idempotency key', async () => {
    applyRemittance.mockResolvedValue({ order_no: 'RMT1' })
    const { wrapper } = mountPage(profile(true))
    await flushPromises()
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
    await Promise.all([wrapper.vm.submit(), wrapper.vm.submit()])
    expect(applyRemittance).toHaveBeenCalledTimes(1)
    expect(applyRemittance.mock.calls[0][0]).toMatchObject({ quote_id: 'RQT1' })
    expect(applyRemittance.mock.calls[0][1]).toBeTruthy()
    expect(push).toHaveBeenCalledWith('/orders')
  })

  it('offers remitter, beneficiary, and shared charge bearer options', async () => {
    const { wrapper } = mountPage(profile(true))
    await flushPromises()
    expect(wrapper.vm.form.fee_bearing).toBe('OUR')
    const values = wrapper.findAll('.el-option-stub').map((node) => node.attributes('data-value'))
    expect(values).toEqual(expect.arrayContaining(['OUR', 'BEN', 'SHA']))
    expect(wrapper.text()).toContain('All charges to be borne by remitter')
    expect(wrapper.text()).toContain('All charges to be borne by beneficiary')
    expect(wrapper.text()).toContain('Charges to be borne by both remitter and beneficiary')
  })

  it('quotes with SHA when shared charges are selected', async () => {
    feePreview.mockResolvedValue({
      quote_id: 'RQT-SHA',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    })
    const { wrapper } = mountPage(profile(true))
    await flushPromises()
    wrapper.vm.form.amount = '1000'
    wrapper.vm.form.fee_bearing = 'SHA'
    await wrapper.vm.preview()
    expect(feePreview).toHaveBeenCalledWith(expect.objectContaining({
      fee_bearing: 'SHA',
      amount: '1000'
    }))
  })
})
