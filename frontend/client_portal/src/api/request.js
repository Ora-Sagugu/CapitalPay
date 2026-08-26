import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 后端 API 前缀：/api -> dev proxy -> http://127.0.0.1:8001
const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

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
