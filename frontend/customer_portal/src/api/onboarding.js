import request from './request'

export function getOnboardingStatus() {
  return request.get('/v1/user/onboarding/status/')
}

export function submitOnboarding(data) {
  return request.post('/v1/user/onboarding/submit/', data)
}
