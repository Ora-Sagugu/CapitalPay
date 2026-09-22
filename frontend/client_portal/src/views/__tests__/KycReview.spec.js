import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

import { i18n } from '@/i18n'
import KycReview from '../KycReview.vue'
import { getOnboardingList, reviewOnboarding } from '@/api/userPortal'

vi.mock('@/api/userPortal', () => ({
  getOnboardingList: vi.fn(),
  getOnboardingDetail: vi.fn(),
  reviewOnboarding: vi.fn(),
  startOnboardingReview: vi.fn()
}))
vi.mock('@/api/merchants', () => ({
  reviewMerchantKyc: vi.fn()
}))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: () => true
  })
}))

function mountAgentOnboarding() {
  return mount(KycReview, {
    props: { embedded: true, portalRole: 'agent' },
    global: { plugins: [i18n, ElementPlus] }
  })
}

describe('agent onboarding queue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    i18n.global.locale.value = 'en-US'
    getOnboardingList.mockResolvedValue({
      items: [
        {
          id: 'u1',
          username: 'grace.agent',
          email: 'grace@example.com',
          legal_person: 'Grace Nyambura',
          onboarding_status: 'pending'
        }
      ],
      total: 1,
      stats: { pending_profile: 1, approved: 0, rejected: 0 }
    })
    reviewOnboarding.mockResolvedValue({ status: 'approved' })
  })

  it('agrees from the list without a Decision form', async () => {
    const wrapper = mountAgentOnboarding()
    await flushPromises()
    expect(wrapper.text()).toContain('Agree')
    expect(wrapper.text()).not.toContain('Decision')
    expect(wrapper.text()).not.toContain('KYC tier')
    expect(wrapper.text()).not.toContain('Commission rate')

    const agree = wrapper.findAll('button').find((btn) => btn.text() === 'Agree')
    expect(agree).toBeTruthy()
    await agree.trigger('click')
    await flushPromises()
    expect(reviewOnboarding).toHaveBeenCalledWith('u1', { action: 'approve', remark: '' })
  })
})
