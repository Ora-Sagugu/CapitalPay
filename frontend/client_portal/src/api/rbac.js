import request from './request'

// 运营用户
export function getUsers(params) {
  return request.get('/v1/admin/users/', { params })
}
export function resetUserPassword(id) {
  return request.post(`/v1/admin/users/${id}/reset-password/`)
}
export function toggleUserStatus(id, data) {
  return request.post(`/v1/admin/users/${id}/toggle-status/`, data)
}
export function assignUserRoles(id, data) {
  return request.post(`/v1/admin/users/${id}/assign-roles/`, data)
}
// 角色
export function getRoles(params) {
  return request.get('/v1/admin/roles/', { params })
}
export function getRolePermissions(id) {
  return request.get(`/v1/admin/roles/${id}/permissions/`)
}
export function grantRolePermission(id, data) {
  return request.post(`/v1/admin/roles/${id}/grant/`, data)
}
// 权限
export function getPermissions(params) {
  return request.get('/v1/admin/permissions/', { params })
}
// 操作日志
export function getOperationLogs(params) {
  return request.get('/v1/admin/logs/', { params })
}
