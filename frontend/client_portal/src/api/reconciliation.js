import request from './request'

// 对账批次：GET /api/v1/admin/recon-batches/
export function getReconBatches(params) {
  return request.get('/v1/admin/recon-batches/', { params })
}

// 对账差异：GET /api/v1/admin/recon-diffs/
export function getReconDiffs(params) {
  return request.get('/v1/admin/recon-diffs/', { params })
}

// Nostro 余额核对：GET /api/v1/admin/nostro-checks/
export function getNostroChecks(params) {
  return request.get('/v1/admin/nostro-checks/', { params })
}
export function resolveReconDiff(id, data) {
  return request.post(`/v1/admin/recon-diffs/${id}/resolve/`, data)
}
export function getReconAlerts(params) {
  return request.get('/v1/admin/recon-alerts/', { params })
}
export function ackReconAlert(id, data) {
  return request.post(`/v1/admin/recon-alerts/${id}/ack/`, data)
}
export function getReconAlertConfig() {
  return request.get('/v1/admin/recon-alert-config/')
}
export function updateReconAlertConfig(data) {
  return request.patch('/v1/admin/recon-alert-config/update/', data)
}
