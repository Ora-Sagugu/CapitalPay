import request from './request'

export function getOnboardingStatus() {
  return request.get('/v1/user/onboarding/status/')
}
export function submitOnboarding(data) {
  return request.post('/v1/user/onboarding/submit/', data)
}
export function uploadOnboardingFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request.post('/v1/user/onboarding/upload/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
