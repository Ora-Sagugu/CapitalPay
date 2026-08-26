import request from './request'

// 银行通道
export function getChannels(params) {
  return request.get('/v1/admin/channels/', { params })
}
export function toggleChannelStatus(id, data) {
  return request.post(`/v1/admin/channels/${id}/toggle-status/`, data)
}
export function getChannelTransactions(id, params) {
  return request.get(`/v1/admin/channels/${id}/transactions/`, { params })
}
// 路由规则
export function getRoutingRules(params) {
  return request.get('/v1/admin/rules/', { params })
}
export function createRoutingRule(data) {
  return request.post('/v1/admin/rules/', data)
}
// 路由日志（避免与 RBAC /logs/ 冲突）
export function getRoutingLogs(params) {
  return request.get('/v1/admin/routing-logs/', { params })
}
