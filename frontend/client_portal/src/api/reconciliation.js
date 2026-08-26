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
