import request from './request'

export function getUsers(params) {
  return request.get('/v1/admin/users/', { params })
}
export function createUser(data) {
  return request.post('/v1/admin/users/', data)
}
export function updateUser(id, data) {
  return request.patch(`/v1/admin/users/${id}/`, data)
}
export function deleteUser(id) {
  return request.delete(`/v1/admin/users/${id}/`)
}
export function resetUserPassword(id, data) {
  return request.post(`/v1/admin/users/${id}/reset-password/`, data)
}
export function toggleUserStatus(id, data) {
  return request.post(`/v1/admin/users/${id}/toggle-status/`, data)
}
export function assignUserRoles(id, data) {
  return request.post(`/v1/admin/users/${id}/assign-roles/`, data)
}
export function getRoles(params) {
  return request.get('/v1/admin/roles/', { params })
}
export function createRole(data) {
  return request.post('/v1/admin/roles/', data)
}
export function updateRole(id, data) {
  return request.patch(`/v1/admin/roles/${id}/`, data)
}
export function deleteRole(id) {
  return request.delete(`/v1/admin/roles/${id}/`)
}
export function getRolePermissions(id) {
  return request.get(`/v1/admin/roles/${id}/permissions/`)
}
export function grantRolePermission(id, data) {
  return request.post(`/v1/admin/roles/${id}/grant/`, data)
}
export function getPermissions(params) {
  return request.get('/v1/admin/permissions/', { params })
}
export function getFunctions() {
  return request.get('/v1/admin/functions/')
}
export function setFunctionRoles(code, data) {
  return request.put(`/v1/admin/functions/${encodeURIComponent(code)}/roles/`, data)
}
export function setRoleCapabilities(id, data) {
  return request.put(`/v1/admin/roles/${id}/capabilities/`, data)
}
export function getOperationLogs(params) {
  return request.get('/v1/admin/logs/', { params })
}
export function getEndUsers(params) {
  return request.get('/v1/admin/end-users/list/', { params })
}
export function toggleEndUser(id) {
  return request.post(`/v1/admin/end-users/${id}/toggle-status/`)
}
export function deleteEndUser(id) {
  return request.post(`/v1/admin/end-users/${id}/delete/`)
}
