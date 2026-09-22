import request from './request'

export function registerByPhone(data) {
  return request.post('/v1/user/auth/register/', data)
}

export function registerByEmail(data) {
  return request.post('/v1/user/auth/register-email/', data)
}

export function loginByPassword(data) {
  return request.post('/v1/user/auth/login/password/', data)
}

export function loginByEmail(data) {
  return request.post('/v1/user/auth/login/email/', data)
}

export function loginBySms(data) {
  return request.post('/v1/user/auth/login/sms/', data)
}

export function sendSmsCode(data) {
  return request.post('/v1/user/auth/sms/send/', data)
}

export function getProfile() {
  return request.get('/v1/user/profile/me/')
}
