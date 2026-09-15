import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import AgentRemittance from '../AgentRemittance.vue'
import {
  agentRemittanceApply,
  agentRemittanceQuote,
  getAgentMerchants
} from '@/api/agent'
import { getProfile } from '@/api/auth'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ query: {} })
}))
vi.mock('@/api/agent', () => ({
  getAgentMerchants: vi.fn(),
  agentRemittanceQuote: vi.fn(),
  agentRemittanceApply: vi.fn(),
  agentSanctionCheck: vi.fn()
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

const eligibleMerchant = {
  id: 'm-1',
  merchant_no: 'M001',
  merchant_name: 'Alpha Co',
  remittance_eligibility: { eligible: true, blockers: [] }
}
const eligibleMerchantB = {
  id: 'm-3',
  merchant_no: 'M003',
  merchant_name: 'Gamma Co',
  remittance_eligibility: { eligible: true, blockers: [] }
}
const blockedMerchant = {
  id: 'm-2',
  merchant_no: 'M002',
  merchant_name: 'Beta Co',
  remittance_eligibility: {
    eligible: false,
    blockers: [{ code: 'KYC_NOT_APPROVED', message: 'KYC pending' }]
  }
}

function mountPage(merchantItems = [eligibleMerchant, eligibleMerchantB, blockedMerchant]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = {
    portal_role: 'agent',
    onboarding_status: 'approved',
    remittance_eligibility: { eligible: false, blockers: [] }
  }
  getProfile.mockResolvedValue(auth.user)
  getAgentMerchants.mockResolvedValue({ items: merchantItems })
  return { wrapper: mount(AgentRemittance, {
    global: { plugins: [pinia, i18n], stubs }
  }), auth }
}

describe('agent proxy remittance', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  it('loads customers and keeps submit gated until one is selected', async () => {
    const { wrapper } = mountPage()
    await flushPromises()
    expect(getAgentMerchants).toHaveBeenCalled()
    expect(wrapper.vm.merchants).toHaveLength(3)
    expect(wrapper.vm.form.merchant_id).toBe('')
    expect(wrapper.vm.formEnabled).toBe(true)
    expect(wrapper.find('.remittance-form').attributes('data-disabled')).toBe('false')
    expect(wrapper.vm.canSubmit).toBe(false)
    expect(agentRemittanceQuote).not.toHaveBeenCalled()
  })

  it('auto-selects the only eligible customer so the form is usable', async () => {
    const { wrapper } = mountPage([eligibleMerchant])
    await flushPromises()
    expect(wrapper.vm.form.merchant_id).toBe('m-1')
    expect(wrapper.vm.canSubmit).toBe(true)
    expect(wrapper.find('.remittance-form').attributes('data-disabled')).toBe('false')
  })

  it('quotes only after an eligible customer and amount are set', async () => {
    agentRemittanceQuote.mockResolvedValue({
      quote_id: 'RQT-AG-1',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    })
    const { wrapper } = mountPage()
    await flushPromises()
    wrapper.vm.form.merchant_id = 'm-1'
    wrapper.vm.form.amount = '250'
    await wrapper.vm.preview()
    expect(agentRemittanceQuote).toHaveBeenCalledWith(expect.objectContaining({
      merchant_id: 'm-1',
      amount: '250',
      fee_bearing: 'OUR'
    }))
  })

  it('offers remitter, beneficiary, and shared charge bearer options', async () => {
    const { wrapper } = mountPage()
    await flushPromises()
    expect(wrapper.vm.form.fee_bearing).toBe('OUR')
    const values = wrapper.findAll('.el-option-stub').map((node) => node.attributes('data-value'))
    expect(values).toEqual(expect.arrayContaining(['OUR', 'BEN', 'SHA']))
    expect(wrapper.text()).toContain('All charges to be borne by remitter')
    expect(wrapper.text()).toContain('All charges to be borne by beneficiary')
    expect(wrapper.text()).toContain('Charges to be borne by both remitter and beneficiary')
  })

  it('quotes with SHA when shared charges are selected', async () => {
    agentRemittanceQuote.mockResolvedValue({
      quote_id: 'RQT-AG-SHA',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    })
    const { wrapper } = mountPage()
    await flushPromises()
    wrapper.vm.form.merchant_id = 'm-1'
    wrapper.vm.form.amount = '250'
    wrapper.vm.form.fee_bearing = 'SHA'
    await wrapper.vm.preview()
    expect(agentRemittanceQuote).toHaveBeenCalledWith(expect.objectContaining({
      merchant_id: 'm-1',
      amount: '250',
      fee_bearing: 'SHA'
    }))
  })

  it('submits with merchant_id and navigates to agent orders', async () => {
    agentRemittanceApply.mockResolvedValue({
      order_no: 'RMT-AG-1',
      status: 'PENDING_REVIEW'
    })
    const { wrapper } = mountPage()
    await flushPromises()
    wrapper.vm.form.merchant_id = 'm-1'
    Object.assign(wrapper.vm.form, {
      amount: '100',
      beneficiary_name: 'Supplier',
      beneficiary_account: '001',
      beneficiary_bank: 'Bank'
    })
    wrapper.vm.fee = {
      quote_id: 'RQT-AG-1',
      expires_at: new Date(Date.now() + 60_000).toISOString()
    }
    await wrapper.vm.submit()
    expect(agentRemittanceApply).toHaveBeenCalledTimes(1)
    expect(agentRemittanceApply.mock.calls[0][0]).toMatchObject({
      merchant_id: 'm-1',
      quote_id: 'RQT-AG-1'
    })
    expect(push).toHaveBeenCalledWith('/agent/orders')
  })

  it('blocks submit when no quote exists', async () => {
    const { wrapper } = mountPage()
    await flushPromises()
    wrapper.vm.form.merchant_id = 'm-1'
    Object.assign(wrapper.vm.form, {
      amount: '100',
      beneficiary_name: 'Supplier',
      beneficiary_account: '001',
      beneficiary_bank: 'Bank'
    })
    wrapper.vm.fee = null
    await wrapper.vm.submit()
    expect(agentRemittanceApply).not.toHaveBeenCalled()
  })
})
