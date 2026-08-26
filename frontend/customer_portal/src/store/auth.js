import { defineStore } from 'pinia'
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
      state.user?.real_name || state.user?.nickname || state.user?.username || '客户',
    onboardingStatus: (state) => state.user?.onboarding_status || 'none'
  },
  actions: {
    setSession(data) {
      this.token = data.token
      this.user = data.user
      persistAuth(data.token, data.user)
      return data
    },
    async loginByPhonePassword(phone, password) {
      return this.setSession(await loginByPassword({ phone, password }))
    },
    async loginByEmailPassword(email, password) {
      return this.setSession(await loginByEmail({ email, password }))
    },
    async loginByPhoneSms(phone, sms_code) {
      return this.setSession(await loginBySms({ phone, sms_code }))
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
