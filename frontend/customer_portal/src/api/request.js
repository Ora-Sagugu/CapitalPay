import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

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
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      ElMessage.error('登录已过期，请重新登录')
      router.replace({ name: 'login' })
    } else {
      let msg = '请求失败'
      if (data) {
        if (typeof data === 'string') msg = data
        else if (data.message) msg = data.message
        else if (data.detail) msg = data.detail
        else if (data.code) msg = data.code
      }
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export default service
