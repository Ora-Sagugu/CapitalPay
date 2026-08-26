import request from './request'

// 运营后台登录：POST /api/v1/admin/auth/login/
// 请求体: { account, password }
// 响应:   { token, expires_in, user{id,username,real_name,phone,email,roles,permissions}, license_warnings }
export function login(data) {
  return request.post('/v1/admin/auth/login/', data)
}

// 登出：POST /api/v1/admin/auth/logout/
export function logout() {
  return request.post('/v1/admin/auth/logout/')
}

// 当前用户：GET /api/v1/admin/auth/me/
export function me() {
  return request.get('/v1/admin/auth/me/')
}
