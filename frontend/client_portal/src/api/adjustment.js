import request from './request'

export function getAdjustments(params) {
  return request.get('/v1/admin/applications/', { params })
}
export function createAdjustment(data) {
  return request.post('/v1/admin/applications/', data)
}
export function getAdjustmentDetail(id) {
  return request.get(`/v1/admin/applications/${id}/`)
}
export function approveAdjustment(id, data = {}) {
  return request.post(`/v1/admin/applications/${id}/approve/`, data)
}
export function rejectAdjustment(id, data = {}) {
  return request.post(`/v1/admin/applications/${id}/reject/`, data)
}
export function getAdjustmentStats() {
  return request.get('/v1/admin/applications/stats/')
}
