import request from './request'

export function getOnboardingList(params) {
  return request.get('/v1/admin/onboarding/', { params })
}
export function getOnboardingDetail(id) {
  return request.get(`/v1/admin/onboarding/${id}/detail/`)
}
export function reviewOnboarding(id, data) {
  return request.post(`/v1/admin/onboarding/${id}/review/`, data)
}
export function startOnboardingReview(id) {
  return request.post(`/v1/admin/onboarding/${id}/start-review/`)
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
