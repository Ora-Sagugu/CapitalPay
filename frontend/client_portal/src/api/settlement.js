import request from './request'

// 结算批次
export function getSettleBatches(params) {
  return request.get('/v1/admin/settle-batches/', { params })
}
export function getSettleBatchDetail(id) {
  return request.get(`/v1/admin/settle-batches/${id}/`)
}
export function approveSettleBatch(id) {
  return request.post(`/v1/admin/settle-batches/${id}/approve/`)
}
export function exportSettleBatch(id) {
  return request.post(`/v1/admin/settle-batches/${id}/export/`)
}
export function getSettleBatchStats() {
  return request.get('/v1/admin/settle-batches/stats/')
}
// 结算明细
export function getSettleDetails(params) {
  return request.get('/v1/admin/settle-details/', { params })
}
// 分润
export function getFeeShares(params) {
  return request.get('/v1/admin/fee-shares/', { params })
}
// 差异核销
export function getDifferenceWriteoffs(params) {
  return request.get('/v1/admin/difference-writeoffs/', { params })
}
