import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import RemittanceApply from '../RemittanceApply.vue'
import { applyRemittance, feePreview, sanctionCheck } from '@/api/payments'
import { getProfile } from '@/api/auth'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() })
}))
vi.mock('@/api/payments', () => ({
  applyRemittance: vi.fn(),
  feePreview: vi.fn(),
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
  'el-row': passthrough,
  'el-col': passthrough,
  'el-form-item': passthrough,
  'el-select': passthrough,
  'el-option': passthrough,
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'input', 'blur'],
    template: `
      <input
        class="el-input-stub"
        :value="modelValue"
        @input="$emit('update:modelValue', $event.target.value); $emit('input', $event)"
        @blur="$emit('blur', $event)"
      />
    `
  },
  'el-radio-group': passthrough,
  'el-radio-button': passthrough,
  'el-button': passthrough,
  'el-form': {
    props: ['disabled'],
    template: '<form class="remittance-form" :data-disabled="String(Boolean(disabled))"><slot /></form>'
  },
  'el-alert': {
    props: ['title', 'description', 'type'],
    template: '<div class="sanction-alert" :data-type="type"><div class="alert-title">{{ title }}</div><div class="alert-desc">{{ description }}</div></div>'
  }
}

function profile(eligible = true) {
  return {
    onboarding_status: 'approved',
    merchant_status: 'ACTIVE',
    activation_stage: 'ACTIVE',
    remittance_eligibility: {
      eligible,
      blockers: eligible ? [] : [{ code: 'MERCHANT_PENDING', message: 'Pending' }]
    }
  }
}

function mountPage(currentProfile = profile(true)) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = currentProfile
  getProfile.mockResolvedValue(currentProfile)
  feePreview.mockResolvedValue({
    quote_id: 'Q1',
    expires_at: new Date(Date.now() + 60_000).toISOString(),
    total_fee: '1',
    fee_currency: 'USD',
    sender_total: '101',
    from_currency: 'USD',
    settle_amount: '100',
    to_currency: 'USD'
  })
  return mount(RemittanceApply, {
    global: { plugins: [pinia, i18n], stubs }
  })
}

describe('remittance sanctions warning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows a warning when Iran is entered as beneficiary name', async () => {
    sanctionCheck.mockResolvedValue({
      total_hits: 1,
      warning_message: 'Sanctions warning: input matches sanctioned jurisdiction Iran (OFAC/UN).'
    })
    const wrapper = mountPage()
    await flushPromises()
    wrapper.vm.form.beneficiary_name = 'Iran'
    wrapper.vm.onBeneficiaryInput()
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(sanctionCheck).toHaveBeenCalledWith({
      beneficiary_name: 'Iran',
      beneficiary_address: ''
    })
    expect(wrapper.find('.sanction-alert').exists()).toBe(true)
    expect(wrapper.find('.sanction-alert .alert-desc').text()).toContain('Iran')
  })

  it('hides the warning when beneficiary fields are cleared', async () => {
    sanctionCheck.mockResolvedValue({
      total_hits: 1,
      warning_message: 'Sanctions warning: input matches sanctioned jurisdiction Iran (OFAC/UN).'
    })
    const wrapper = mountPage()
    await flushPromises()
    wrapper.vm.form.beneficiary_name = 'Iran'
    await wrapper.vm.runSanctionCheck()
    await flushPromises()
    expect(wrapper.find('.sanction-alert').exists()).toBe(true)

    wrapper.vm.form.beneficiary_name = ''
    wrapper.vm.onBeneficiaryInput()
    await flushPromises()
    expect(wrapper.find('.sanction-alert').exists()).toBe(false)
  })
})
