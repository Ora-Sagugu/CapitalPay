import request from './request'

export function getChannels(params) {
  return request.get('/v1/admin/channels/', { params })
}
export function getChannel(id) {
  return request.get(`/v1/admin/channels/${id}/`)
}
export function getChannelStats() {
  return request.get('/v1/admin/channels/stats/')
}
export function createChannel(data) {
  return request.post('/v1/admin/channels/', data)
}
export function updateChannel(id, data) {
  return request.put(`/v1/admin/channels/${id}/`, data)
}
export function toggleChannelStatus(id, data) {
  return request.post(`/v1/admin/channels/${id}/toggle-status/`, data)
}
export function getChannelTransactions(id, params) {
  return request.get(`/v1/admin/channels/${id}/transactions/`, { params })
}
export function getRoutingRules(params) {
  return request.get('/v1/admin/rules/', { params })
}
export function createRoutingRule(data) {
  return request.post('/v1/admin/rules/', data)
}
export function getRoutingLogs(params) {
  return request.get('/v1/admin/routing-logs/', { params })
}
