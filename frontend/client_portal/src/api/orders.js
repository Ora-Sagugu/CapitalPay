import request from './request'

export function getOrders(params) {
  return request.get('/v1/admin/orders/', { params })
}
export function getOrderDetail(orderNo) {
  return request.get(`/v1/admin/orders/${orderNo}/`)
}
export function getOrderSanctionReview(orderNo) {
  return request.get(`/v1/admin/orders/${orderNo}/sanction-review/`)
}
export function applyRemittance(data, idempotencyKey) {
  return request.post('/v1/admin/orders/apply/', data, {
    headers: { 'Idempotency-Key': idempotencyKey }
  })
}
export function reviewOrder(orderNo, data) {
  return request.post(`/v1/admin/orders/${orderNo}/review/`, data)
}
export function confirmPayment(orderNo, data = {}) {
  return request.post(`/v1/admin/orders/${orderNo}/confirm-payment/`, data)
}
export function confirmTransfer(orderNo, data = {}) {
  return request.post(`/v1/admin/orders/${orderNo}/confirm-transfer/`, data)
}
export function getPayoutBanks(orderNo) {
  return request.get(`/v1/admin/orders/${orderNo}/payout-banks/`)
}
export function closeOrder(orderNo, data = {}) {
  return request.post(`/v1/admin/orders/${orderNo}/close/`, data)
}
export function feePreview(params) {
  return request.post('/v1/admin/orders/quote/', params)
}
export function sanctionCheck(data) {
  return request.post('/v1/admin/orders/sanction-check/', data)
}
export function getPreorders(params) {
  return request.get('/v1/admin/orders/preorders/', { params })
}
export function getPreorderStats() {
  return request.get('/v1/admin/orders/preorder-stats/')
}
export function traceFund(params) {
  return request.get('/v1/admin/orders/trace-fund/', { params })
}
export function initiateOrderRefund(orderNo, data) {
  return request.post(`/v1/admin/orders/${orderNo}/refund-initiate/`, data)
}
