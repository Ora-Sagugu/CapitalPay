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
  (response) => {
    // #region agent log
    const url = response?.config?.url || ''
    if (/\/user\/(agent\/)?(merchants|customers|kyc)/.test(url)) {
      fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'F',location:'request.js:response:ok',message:'api ok',data:{url,status:response.status,method:response.config?.method||'get',debugMerchants:response.headers?.['x-debug-merchants']||'',params:response.config?.params||null},timestamp:Date.now()})}).catch(()=>{});
    }
    // #endregion
    return response.data
  },
  async (error) => {
    const status = error.response?.status
    const transportMessage = describeTransportError(error)
    const isAuthRequest = /\/(login|register|refresh)/.test(error.config?.url || '')
    const data = await parseResponseData(error.response?.data)
    // #region agent log
    {
      const url = error.config?.url || ''
      if (/\/user\/(agent\/)?(merchants|customers|kyc)/.test(url) || (data && String(data.message||data.detail||'').includes('merchant portal'))) {
        fetch('http://127.0.0.1:7400/ingest/4ebbb499-0df2-4dae-83ef-65d3a7131853',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'ce1e79'},body:JSON.stringify({sessionId:'ce1e79',runId:'post-fix',hypothesisId:'B',location:'request.js:response:err',message:'api error',data:{url,status:status||0,code:data?.code||'',apiMessage:data?.message||data?.detail||'',skipErrorToast:!!error.config?.skipErrorToast},timestamp:Date.now()})}).catch(()=>{});
      }
    }
    // #endregion
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
