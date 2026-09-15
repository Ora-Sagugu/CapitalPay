import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import {
  describeTransportError,
  extractErrorMessage,
  parseResponseData
} from './error'

export { extractErrorMessage } from './error'

// 后端 API 前缀：/api -> dev proxy -> http://127.0.0.1:1024
const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

let handlingUnauthorized = false

// 请求拦截：注入 JWT
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

// 响应拦截：统一拆包 + 错误处理
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
        await router.replace({ name: 'login' })
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
