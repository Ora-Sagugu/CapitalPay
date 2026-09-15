import axios from 'axios'
import { ElMessage } from 'element-plus'
import { defaultLoginRouteName, getPortalMode } from '@/config/portal'
import router from '@/router'
import {
  describeTransportError,
  extractErrorMessage,
  parseResponseData
} from './error'

export { extractErrorMessage } from './error'

const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

let handlingUnauthorized = false

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const status = error.response?.status
    const transportMessage = describeTransportError(error)
    const isAuthRequest = /\/(login|register|refresh)/.test(error.config?.url || '')
    const data = await parseResponseData(error.response?.data)
    if (status === 401 && !isAuthRequest) {
      if (!handlingUnauthorized) {
        handlingUnauthorized = true
        const { useAuthStore } = await import('@/store/auth')
        useAuthStore().logout()
        ElMessage.error(extractErrorMessage(data, 'The session has expired. Authenticate again.'))
        const loginName = getPortalMode() === 'agent' || !router.currentRoute.value.path.startsWith('/agent')
          ? defaultLoginRouteName()
          : 'agent-login'
        await router.replace({ name: loginName })
        setTimeout(() => { handlingUnauthorized = false }, 500)
      }
    } else {
      const message = transportMessage || extractErrorMessage(data)
      if (message && !error.config?.skipErrorToast) {
        ElMessage.error(message)
      }
    }
    return Promise.reject(error)
  }
)

export default service
