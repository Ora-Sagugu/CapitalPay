import request from './request'

export function getBankNotifications(params) {
  return request.get('/v1/admin/bank-notifications/', { params })
}

export function getBankNotificationDetail(notificationNo) {
  return request.get(`/v1/admin/bank-notifications/${notificationNo}/`)
}

export function getBankNotificationStats() {
  return request.get('/v1/admin/bank-notifications/stats/')
}

export function simulateBankCredit(data) {
  return request.post('/v1/admin/bank-notifications/simulate/', data)
}
