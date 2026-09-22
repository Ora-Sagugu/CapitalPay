import request from './request'

export function getAgentProfile() {
  return request.get('/v1/user/agent/me/')
}

export function getAgentEarnings(params) {
  return request.get('/v1/user/agent/earnings/', { params })
}

export function getAgentMerchants(params, config = {}) {
  return request.get('/v1/user/agent/merchants/', {
    params: { ...(params || {}), _ts: Date.now() },
    headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
    skipErrorToast: true,
    ...config
  })
}

export function getAgentCustomers(params, config = {}) {
  return request.get('/v1/user/agent/customers/', { params, skipErrorToast: true, ...config })
}

export function getAgentKycList(params, config = {}) {
  return request.get('/v1/user/agent/kyc/', { params, skipErrorToast: true, ...config })
}

export function getAgentKycDetail(userId) {
  return request.get(`/v1/user/agent/kyc/${userId}/`)
}

export function reviewAgentKyc(userId, data) {
  return request.post(`/v1/user/agent/kyc/${userId}/review/`, data)
}

export function getAgentOrders(params) {
  return request.get('/v1/user/agent/orders/', { params })
}

export function getAgentOrderDetail(orderNo) {
  return request.get(`/v1/user/agent/orders/${orderNo}/`)
}
