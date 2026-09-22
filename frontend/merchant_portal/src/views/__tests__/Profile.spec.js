import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import { useAuthStore } from '@/store/auth'
import Profile from '../Profile.vue'
import { getProfile } from '@/api/auth'
import { getOnboardingStatus } from '@/api/onboarding'

vi.mock('@/api/auth', () => ({
  loginByPassword: vi.fn(),
  loginByEmail: vi.fn(),
  loginBySms: vi.fn(),
  registerByPhone: vi.fn(),
  registerByEmail: vi.fn(),
  getProfile: vi.fn()
}))
vi.mock('@/api/onboarding', () => ({
  getOnboardingStatus: vi.fn(),
  submitOnboarding: vi.fn(),
  uploadOnboardingFile: vi.fn()
}))

function mountPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.token = 'token'
  auth.user = { onboarding_status: 'approved', portal_role: 'merchant' }
  return mount(Profile, {
    global: { plugins: [pinia, i18n, ElementPlus] }
  })
}

describe('merchant profile page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    i18n.global.locale.value = 'en-US'
    getProfile.mockResolvedValue({
      real_name: 'Amara Wanjiku',
      phone: '254***0101',
      email: 'amarawanjiku@gmail.com',
      onboarding_status: 'approved',
      merchant_no: 'M1001',
      merchant_name: 'Horizon Trade Limited',
      merchant_status: 'ACTIVE',
      merchant_kyc_status: 'APPROVED',
      agent_name: 'Grace Nyambura Agency',
      agent_no: 'AG20260001'
    })
    getOnboardingStatus.mockResolvedValue({
      onboarding_status: 'approved',
      data: {
        basic: {
          legal_name: 'Amara Wanjiku',
          id_type: 'passport',
          id_number: 'A1234567',
          contact_phone: '254712000101',
          nationality: 'Kenya',
          address: 'Nairobi CBD',
          license_expiry_date: '2027-12-31'
        }
      }
    })
  })

  it('shows personal identity fields at the top of the merchant workspace', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Profile')
    expect(wrapper.get('[data-testid="profile-basic"]').text()).toContain('Amara Wanjiku')
    expect(wrapper.get('[data-testid="profile-basic"]').text()).toContain('A1234567')
    expect(wrapper.get('[data-testid="profile-basic"]').text()).toContain('Kenya')
    expect(wrapper.get('[data-testid="profile-basic"]').text()).toContain('Nairobi CBD')
    expect(wrapper.get('[data-testid="profile-merchant"]').text()).toContain('M1001')
    expect(wrapper.get('[data-testid="profile-merchant"]').text()).toContain('Horizon Trade Limited')
    expect(wrapper.get('[data-testid="profile-merchant"]').text()).toContain('Grace Nyambura Agency')
    expect(wrapper.get('[data-testid="profile-merchant"]').text()).toContain('AG20260001')
    expect(getProfile).toHaveBeenCalled()
    expect(getOnboardingStatus).toHaveBeenCalled()
  })
})
