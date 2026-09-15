import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import OnboardingWizard from '../OnboardingWizard.vue'
import { getOnboardingStatus } from '@/api/onboarding'

vi.mock('@/api/onboarding', () => ({
  getOnboardingStatus: vi.fn(),
  submitOnboarding: vi.fn(),
  uploadOnboardingFile: vi.fn()
}))

const passthrough = { template: '<div><slot /></div>' }
const stubs = {
  'el-steps': passthrough,
  'el-step': { props: ['title'], template: '<div class="step">{{ title }}</div>' },
  'el-form': { template: '<form class="onboarding-form"><slot /></form>' },
  'el-form-item': { props: ['label'], template: '<div class="form-item"><slot /></div>' },
  'el-input': passthrough,
  'el-select': passthrough,
  'el-option': passthrough,
  'el-date-picker': passthrough,
  'el-upload': { template: '<div class="upload"><slot /></div>' },
  'el-button': { template: '<button><slot /></button>' },
  'el-descriptions': passthrough,
  'el-descriptions-item': {
    props: ['label'],
    template: '<div class="desc-item"><span class="desc-label">{{ label }}</span><slot /></div>'
  },
  'el-timeline': { template: '<div class="timeline"><slot /></div>' },
  'el-timeline-item': {
    props: ['timestamp'],
    template: '<div class="timeline-item"><slot /></div>'
  },
  'el-alert': {
    props: ['title', 'type', 'description'],
    template: '<div class="onboarding-alert"><div class="alert-title">{{ title }}</div><div class="alert-desc">{{ description }}</div></div>'
  }
}

const profileData = {
  basic: {
    legal_name: 'Acme Ltd',
    id_type: 'id_card',
    id_number: '1234567890',
    contact_phone: '254712345001',
    nationality: 'KE',
    address: 'Nairobi'
  },
  finance: {
    bank_name: 'Equity Bank',
    branch_name: 'Westlands',
    account_name: 'Acme Ltd',
    bank_account: '0011223344'
  },
  images: {
    license_image: 'kyc/20260831/license.png',
    id_front_image: 'kyc/20260831/front.png',
    id_back_image: 'kyc/20260831/back.png'
  }
}

function statusPayload(overrides = {}) {
  return {
    onboarding_status: 'none',
    submitted_at: null,
    reviewed_at: null,
    reviewer: '',
    remark: '',
    data: null,
    ...overrides
  }
}

function mountPage(user = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'none', ...user }
  return mount(OnboardingWizard, {
    global: { plugins: [pinia, i18n], stubs }
  })
}

describe('customer onboarding wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  it('shows the editable wizard when onboarding has not been submitted', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({ onboarding_status: 'none' }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.onboarding-wizard').exists()).toBe(true)
    expect(wrapper.find('.onboarding-form').exists()).toBe(true)
    expect(wrapper.find('.onboarding-summary').exists()).toBe(false)
    expect(wrapper.find('.upload').exists()).toBe(false)
  })

  it('shows a read-only summary and progress after a pending submission', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'pending',
      submitted_at: '2026-08-31T10:00:00Z',
      data: profileData
    }))
    const wrapper = mountPage({ portal_role: 'customer' })
    await flushPromises()
    expect(wrapper.find('.onboarding-wizard').exists()).toBe(false)
    expect(wrapper.find('.onboarding-form').exists()).toBe(false)
    expect(wrapper.find('.upload').exists()).toBe(false)
    expect(wrapper.find('.onboarding-summary').exists()).toBe(true)
    expect(wrapper.find('.onboarding-timeline').exists()).toBe(true)
    expect(wrapper.text()).toContain('Acme Ltd')
    expect(wrapper.text()).toContain('****7890')
    expect(wrapper.text()).toContain('Equity Bank')
    expect(wrapper.text()).toContain('Financial Details')
    expect(wrapper.text()).not.toContain('Wallet Service')
    expect(wrapper.text()).toContain('Submitted for review')
    expect(wrapper.text()).not.toContain('Submit for Review')
  })

  it('keeps financial details off the agent summary', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'pending',
      submitted_at: '2026-08-31T10:00:00Z',
      data: profileData
    }))
    const wrapper = mountPage({ portal_role: 'agent' })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Equity Bank')
    expect(wrapper.text()).not.toContain('Financial Details')
  })

  it('shows agent then operations progress after a referred submission', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'pending',
      submitted_at: '2026-08-31T10:00:00Z',
      agent_review_status: 'pending',
      data: profileData
    }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.onboarding-summary').exists()).toBe(true)
    expect(wrapper.find('.onboarding-alert').exists()).toBe(false)
    expect(wrapper.text()).toContain('Waiting for Agent Review')
    expect(wrapper.text()).toContain('Operations Review')
  })

  it('returns to the editable wizard after rejection', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'rejected',
      submitted_at: '2026-08-31T10:00:00Z',
      reviewed_at: '2026-08-31T12:00:00Z',
      remark: 'ID image is illegible',
      data: profileData
    }))
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.onboarding-wizard').exists()).toBe(true)
    expect(wrapper.find('.onboarding-summary').exists()).toBe(false)
    expect(wrapper.find('.onboarding-alert').exists()).toBe(false)
  })

  it('shows agent code and name on the customer summary', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'pending',
      submitted_at: '2026-08-31T10:00:00Z',
      data: {
        ...profileData,
        basic: {
          ...profileData.basic,
          agent_code: 'kP8mQ2xR',
          agent_name: 'Referral Agent'
        }
      }
    }))
    const wrapper = mountPage({ portal_role: 'customer' })
    await flushPromises()
    expect(wrapper.find('.onboarding-summary').exists()).toBe(true)
    const labels = wrapper.findAll('.desc-label').map((n) => n.text())
    expect(labels).toContain('Agent Code')
    expect(labels).toContain('Agent Name')
    expect(wrapper.text()).toContain('kP8mQ2xR')
    expect(wrapper.text()).toContain('Referral Agent')
  })

  it('hides the agent section for agent-role users', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({
      onboarding_status: 'pending',
      submitted_at: '2026-08-31T10:00:00Z',
      data: {
        ...profileData,
        basic: {
          ...profileData.basic,
          agent_code: 'kP8mQ2xR',
          agent_name: 'Referral Agent'
        }
      }
    }))
    const wrapper = mountPage({ portal_role: 'agent' })
    await flushPromises()
    expect(wrapper.find('.onboarding-summary').exists()).toBe(true)
    const labels = wrapper.findAll('.desc-label').map((n) => n.text())
    expect(labels).not.toContain('Agent Code')
    expect(labels).not.toContain('Agent Name')
    expect(wrapper.text()).not.toContain('kP8mQ2xR')
    expect(wrapper.text()).not.toContain('Referral Agent')
  })
})
