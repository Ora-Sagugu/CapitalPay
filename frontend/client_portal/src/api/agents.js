import request from './request'

export function getAgents(params) {
  return request.get('/v1/admin/agents/', { params })
}
export function activateAgent(id) {
  return request.post(`/v1/admin/agents/${id}/activate/`)
}
export function suspendAgent(id) {
  return request.post(`/v1/admin/agents/${id}/suspend/`)
}
export function getAgentMerchants(params) {
  return request.get('/v1/admin/agent-merchants/', { params })
}
export function getAgentCommissions(params) {
  return request.get('/v1/admin/agent-commissions/', { params })
}
export function getAgentFeeConfigs(params) {
  return request.get('/v1/admin/agent-fee-configs/', { params })
}
export function getAgentKycList(params) {
  return request.get('/v1/admin/agent-kyc/', { params })
}
export function createAgentKyc(data) {
  return request.post('/v1/admin/agent-kyc/', data)
}
export function submitAgentKyc(id) {
  return request.post(`/v1/admin/agent-kyc/${id}/submit/`)
}
export function reviewAgentKyc(id, data) {
  return request.post(`/v1/admin/agent-kyc/${id}/review/`, data)
}
