import { defineStore } from 'pinia'
import { login as apiLogin, logout as apiLogout, me as apiMe } from '@/api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null')
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    displayName: (state) => state.user?.real_name || state.user?.username || '未登录',
    permissions: (state) => state.user?.permissions || [],
    roles: (state) => state.user?.roles || []
  },
  actions: {
    hasPermission(code) {
      const roles = this.roles || []
      if (roles.includes('super_admin') || roles.some((r) => (r?.code || r) === 'super_admin')) {
        return true
      }
      const perms = this.permissions || []
      if (!perms.length) return true // 无权限列表时不阻断菜单（兼容旧 token）
      return perms.includes(code) || perms.some((p) => (p?.code || p) === code)
    },
    async login(account, password) {
      const data = await apiLogin({ account, password })
      this.token = data.token
      this.user = data.user
      localStorage.setItem('token', data.token)
      localStorage.setItem('user', JSON.stringify(data.user))
      return data
    },
    async fetchMe() {
      if (!this.token) return
      try {
        const data = await apiMe()
        this.user = data
        localStorage.setItem('user', JSON.stringify(data))
      } catch (e) {
        /* 忽略 */
      }
    },
    async logout() {
      try {
        await apiLogout()
      } catch (e) {
        /* 忽略 */
      }
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})
