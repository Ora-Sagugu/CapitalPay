import request from './request'

export function getSanctionLists(params) {
  return request.get('/v1/admin/sanction-lists/', { params })
}
export function getSanctionStats() {
  return request.get('/v1/admin/sanction-lists/stats/')
}
export function createSanction(data) {
  return request.post('/v1/admin/sanction-lists/', data)
}
export function importSanctionFile(formData) {
  return request.post('/v1/admin/sanction-lists/import-file/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
export function updateSanction(id, data) {
  return request.patch(`/v1/admin/sanction-lists/${id}/`, data)
}
export function deleteSanction(id) {
  return request.delete(`/v1/admin/sanction-lists/${id}/`)
}
export function getSanctionScans(params) {
  return request.get('/v1/admin/sanction-scans/', { params })
}
export function createSanctionScan(data) {
  return request.post('/v1/admin/sanction-scans/scan/', data)
}
export function getSanctionHits(params) {
  return request.get('/v1/admin/sanction-hits/', { params })
}
