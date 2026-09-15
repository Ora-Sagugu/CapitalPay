import request from './request'

export function getDisbursements(params) {
  return request.get('/v1/admin/disbursements/', { params })
}
export function createDisbursement(data) {
  return request.post('/v1/admin/disbursements/', data)
}
export function approveDisbursement(no, data) {
  return request.post(`/v1/admin/disbursements/${no}/approve/`, data)
}
export function rejectDisbursement(no, data) {
  return request.post(`/v1/admin/disbursements/${no}/reject/`, data)
}
export function executeDisbursement(no) {
  return request.post(`/v1/admin/disbursements/${no}/execute/`)
}
