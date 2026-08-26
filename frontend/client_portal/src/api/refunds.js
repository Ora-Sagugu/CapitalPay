import request from './request'

// 退款订单（admin）
export function getRefunds(params) {
  return request.get('/v1/admin/refunds/', { params })
}
export function getRefundDetail(refundNo) {
  return request.get(`/v1/admin/refunds/${refundNo}/`)
}
export function reviewRefund(refundNo, data) {
  return request.post(`/v1/admin/refunds/${refundNo}/review/`, data)
}
export function initiateRefund(refundNo) {
  return request.post(`/v1/admin/refunds/${refundNo}/execute/`)
}
export function initiateOrderRefund(orderNo, data) {
  return request.post(`/v1/admin/orders/${orderNo}/refund-initiate/`, data)
}
export function getRefundFeeConfig() {
  return request.get('/v1/admin/refunds/fee-config/')
}
export function getRefundStats() {
  return request.get('/v1/admin/refunds/stats/')
}
