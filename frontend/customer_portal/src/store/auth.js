import { defineStore } from 'pinia'
import { defaultLoginRouteName, getPortalMode } from '@/config/portal'
import {
  loginByPassword,
  loginByEmail,
  loginBySms,
  registerByPhone,
  registerByEmail,
  getProfile
} from '@/api/auth'

function persistAuth(token, user) {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null')
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    displayName: (state) =>
      state.user?.real_name || state.user?.nickname || state.user?.username || 'Customer',
    onboardingStatus: (state) => state.user?.onboarding_status || 'none',
    portalRole: (state) => state.user?.portal_role || 'none',
    isAgent: (state) => (state.user?.portal_role || 'none') === 'agent',
    isCustomer: (state) => (state.user?.portal_role || 'none') === 'customer',
    activationStage: (state) => state.user?.activation_stage || 'ONBOARDING_REQUIRED',
    remittanceEligibility: (state) => state.user?.remittance_eligibility || {
      eligible: false,
      blockers: [{ code: 'PROFILE_LOADING', message: 'Verifying customer eligibility' }]
    },
    canRemit() {
      return this.portalRole !== 'agent'
        && this.onboardingStatus === 'approved'
        && this.remittanceEligibility.eligible === true
    }
  },
  actions: {
    setSession(data) {
      this.token = data.token
      this.user = data.user
      persistAuth(data.token, data.user)
      return data
    },
    mergeUser(partial) {
      this.user = { ...(this.user || {}), ...partial }
      if (this.token) persistAuth(this.token, this.user)
    },
    loginRouteName() {
      if (getPortalMode() === 'agent' || this.portalRole !== 'agent') {
        return defaultLoginRouteName()
      }
      return 'agent-login'
    },
    homeRoute(redirect) {
      if (this.portalRole === 'agent') {
        return this.onboardingStatus === 'approved' ? { name: 'agent-overview' } : { name: 'onboarding' }
      }
      const safeRedirect = (
        typeof redirect === 'string'
        && redirect.startsWith('/')
        && !redirect.startsWith('/agent')
      ) ? redirect : null
      if (this.onboardingStatus === 'approved') {
        return safeRedirect || { name: 'accounts' }
      }
      return { name: 'onboarding' }
    },
    async loginByPhonePassword(phone, password, portalRole = 'customer') {
      return this.setSession(await loginByPassword({ phone, password, portal_role: portalRole }))
    },
    async loginByEmailPassword(email, password, portalRole = 'customer') {
      return this.setSession(await loginByEmail({ email, password, portal_role: portalRole }))
    },
    async loginByPhoneSms(phone, sms_code, portalRole = 'customer') {
      return this.setSession(await loginBySms({ phone, sms_code, portal_role: portalRole }))
    },
    async registerPhone(payload) {
      return this.setSession(await registerByPhone(payload))
    },
    async registerEmail(payload) {
      return this.setSession(await registerByEmail(payload))
    },
    async fetchProfile() {
      if (!this.token) return
      try {
        const data = await getProfile()
        this.user = { ...this.user, ...data }
        localStorage.setItem('user', JSON.stringify(this.user))
      } catch {
        /* ignore */
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})
