import request from './request'

export function getAgents(params) {
  return request.get('/v1/admin/agents/', { params })
}
export function getAgentStats() {
  return request.get('/v1/admin/agents/stats/')
}
export function createAgent(data) {
  return request.post('/v1/admin/agents/', data)
}
export function updateAgent(id, data) {
  return request.patch(`/v1/admin/agents/${id}/`, data)
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
export function createAgentMerchant(data) {
  return request.post('/v1/admin/agent-merchants/', data)
}
export function updateAgentMerchant(id, data) {
  return request.patch(`/v1/admin/agent-merchants/${id}/`, data)
}
export function deleteAgentMerchant(id) {
  return request.delete(`/v1/admin/agent-merchants/${id}/`)
}
export function getAgentCommissions(params) {
  return request.get('/v1/admin/agent-commissions/', { params })
}
export function getAgentFeeOverview(id) {
  return request.get(`/v1/admin/agents/${id}/fee-overview/`)
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
