import request from './request'

// 用户端管理（admin 视角）
export function getOnboardingList(params) {
  return request.get('/v1/admin/onboarding/', { params })
}
export function reviewOnboarding(id, data) {
  return request.post(`/v1/admin/onboarding/${id}/review/`, data)
}
export function bindOnboardingMerchant(id, data) {
  return request.post(`/v1/admin/end-users/${id}/bind-merchant/`, data)
}
export function toggleOnboardingStatus(id, data) {
  return request.post(`/v1/admin/onboarding/${id}/toggle-status/`, data)
}
export function deleteOnboarding(id) {
  return request.post(`/v1/admin/end-users/${id}/delete/`)
}
export function getUserAccounts(params) {
  return request.get('/v1/admin/end-user-accounts/', { params })
}
export function getUserPayments(params) {
  return request.get('/v1/admin/end-user-payments/', { params })
}
