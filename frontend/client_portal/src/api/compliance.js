import request from './request'

// 制裁名单
export function getSanctionLists(params) {
  return request.get('/v1/admin/sanction-lists/', { params })
}
// 制裁扫描
export function getSanctionScans(params) {
  return request.get('/v1/admin/sanction-scans/', { params })
}
export function createSanctionScan(data) {
  return request.post('/v1/admin/sanction-scans/', data)
}
// 制裁命中
export function getSanctionHits(params) {
  return request.get('/v1/admin/sanction-hits/', { params })
}
