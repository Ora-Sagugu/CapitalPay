import request from './request'

export function getDashboard(params) {
  return request.get('/v1/admin/dashboard/', { params })
}

export function getOrderStats() {
  return request.get('/v1/admin/orders/stats/')
}
