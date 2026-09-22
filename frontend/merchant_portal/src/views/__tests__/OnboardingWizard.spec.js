import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import OnboardingWizard from '../OnboardingWizard.vue'
import { getOnboardingStatus, submitOnboarding, uploadOnboardingFile } from '@/api/onboarding'
import { getProfile } from '@/api/auth'

vi.mock('@/api/onboarding', () => ({
  getOnboardingStatus: vi.fn(),
  submitOnboarding: vi.fn(),
  uploadOnboardingFile: vi.fn()
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
  'el-form': {
    template: '<form class="onboarding-form"><slot /></form>',
    methods: {
      validate: () => Promise.resolve(true),
      validateField: () => Promise.resolve(true)
    }
  },
  'el-form-item': { props: ['label'], template: '<div class="form-item"><span class="label">{{ label }}</span><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'disabled'],
    template: '<input class="el-input" :value="modelValue" :disabled="disabled" />'
  },
  'el-select': passthrough,
  'el-option': passthrough,
  'el-upload': { template: '<div class="el-upload"><slot /></div>' },
  'el-button': { template: '<button><slot /></button>' },
  'el-alert': {
    props: ['title'],
    template: '<div class="onboarding-alert">{{ title }}</div>'
  },
  'el-descriptions': passthrough,
  'el-descriptions-item': {
    props: ['label'],
    template: '<div class="desc-item"><span class="desc-label">{{ label }}</span><slot /></div>'
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

let wrapper

async function mountPage(user = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = {
    onboarding_status: 'none',
    portal_role: 'merchant',
    email: 'merchant@example.com',
    ...user
  }
  getProfile.mockResolvedValue(auth.user)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/onboarding', name: 'onboarding', component: { template: '<div />' } },
      { path: '/overview', name: 'overview', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/profile', name: 'profile', component: { template: '<div />' } },
      { path: '/agent', name: 'agent-overview', component: { template: '<div />' } }
    ]
  })
  await router.push({ name: 'onboarding' })
  await router.isReady()
  wrapper = mount(OnboardingWizard, {
    global: { plugins: [pinia, i18n, router], stubs }
  })
  return wrapper
}

describe('merchant onboarding wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('shows the merchant profile form with registration email and new fields', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({ onboarding_status: 'none' }))
    const page = await mountPage({ portal_role: 'merchant', email: 'merchant@example.com' })
    await flushPromises()
    const text = page.text()
    expect(text).toContain('Legal Name')
    expect(text).toContain('Trading address')
    expect(text).toContain('TRN (TAJ)')
    expect(text).toContain('Government photo ID')
    expect(text).toContain('Proof of residential address')
    expect(text).toContain('TRN certificate')
    expect(text).toContain('Agent Code')
    const emailInput = page.findAll('input.el-input').find((el) => el.attributes('disabled') !== undefined)
    expect(emailInput?.element.value).toBe('merchant@example.com')
  })

  it('hides Agent Code for agent onboarding', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({ onboarding_status: 'none' }))
    const page = await mountPage({ portal_role: 'agent', email: 'agent@example.com' })
    await flushPromises()
    expect(page.text()).not.toContain('Agent Code')
  })

  it('submits market, TRN and document uploads with the profile', async () => {
    getOnboardingStatus
      .mockResolvedValueOnce(statusPayload({ onboarding_status: 'none' }))
      .mockResolvedValueOnce(statusPayload({
        onboarding_status: 'pending',
        submitted_at: '2026-09-18T10:00:00Z',
        data: {
          basic: {
            legal_name: 'Acme Ltd',
            id_type: 'passport',
            id_number: 'P123',
            contact_phone: '254700000001',
            nationality: 'JM',
            address: 'Kingston',
            agent_code: 'AG20260001',
            trading_market: 'JM',
            trn: '123-456-789'
          },
          images: {
            government_id_image: 'kyc/id.png',
            proof_of_address_image: 'kyc/address.pdf',
            trn_certificate_image: 'kyc/trn.pdf'
          }
        }
      }))
    submitOnboarding.mockResolvedValue({ message: 'ok' })
    uploadOnboardingFile.mockResolvedValue({ path: 'kyc/id.png' })
    const page = await mountPage({ portal_role: 'merchant', email: 'merchant@example.com' })
    await flushPromises()
    const state = page.vm.$.setupState
    Object.assign(state.basic, {
      legal_name: 'Acme Ltd',
      id_type: 'passport',
      id_number: 'P123',
      contact_phone: '254700000001',
      nationality: 'JM',
      address: 'Kingston',
      agent_code: 'AG20260001',
      trading_market: 'JM',
      trn: '123-456-789'
    })
    Object.assign(state.images, {
      government_id_image: 'kyc/id.png',
      proof_of_address_image: 'kyc/address.pdf',
      trn_certificate_image: 'kyc/trn.pdf'
    })
    await state.onSubmit()
    await flushPromises()
    expect(submitOnboarding).toHaveBeenCalledWith({
      basic: {
        legal_name: 'Acme Ltd',
        id_type: 'passport',
        id_number: 'P123',
        contact_phone: '254700000001',
        nationality: 'JM',
        address: 'Kingston',
        agent_code: 'AG20260001',
        trading_market: 'JM',
        trn: '123-456-789'
      },
      images: {
        government_id_image: 'kyc/id.png',
        proof_of_address_image: 'kyc/address.pdf',
        trn_certificate_image: 'kyc/trn.pdf'
      }
    })
    expect(page.text()).toContain('Pending review')
    expect(page.text()).toContain('Acme Ltd')
    expect(page.text()).toContain('Jamaica (Caribbean)')
  })

  it('enters the merchant workspace when onboarding is approved', async () => {
    getOnboardingStatus.mockResolvedValue(statusPayload({ onboarding_status: 'approved' }))
    const page = await mountPage({ portal_role: 'merchant' })
    await flushPromises()
    expect(page.vm.$router.currentRoute.value.name).toBe('overview')
  })
})
