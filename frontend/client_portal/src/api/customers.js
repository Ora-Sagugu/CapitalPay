import request from './request'

export function getCustomers(params) {
  return request.get('/v1/admin/agent-customers/', { params })
}

export function getCustomer(id) {
  return request.get(`/v1/admin/agent-customers/${id}/`)
}
