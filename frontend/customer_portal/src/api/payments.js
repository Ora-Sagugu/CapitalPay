import request from './request'

export function getPaymentHistory(params) {
  return request.get('/v1/user/payments/history/', { params })
}
export function getOrderDetail(orderNo) {
  return request.get('/v1/user/payments/order-detail/', { params: { order_no: orderNo } })
}
export function applyRemittance(data, idempotencyKey) {
  return request.post('/v1/user/payments/apply/', data, {
    headers: { 'Idempotency-Key': idempotencyKey }
  })
}
export function sanctionCheck(data) {
  return request.post('/v1/user/payments/sanction-check/', data)
}
export function feePreview(params) {
  return request.post('/v1/user/payments/quote/', params)
}
export function getRemittances(params) {
  return request.get('/v1/user/payments/remittances/', { params })
}
export function listBoundAccounts() {
  return request.get('/v1/user/accounts/list/')
}
export function getAccountLedger(params) {
  return request.get('/v1/user/accounts/virtual/ledger/', { params })
}
export function getCurrencies() {
  return request.get('/v1/user/accounts/currencies/')
}
export function bindAccount(data) {
  return request.post('/v1/user/accounts/bind/', data)
}
export function unbindAccount(data) {
  return request.post('/v1/user/accounts/unbind/', data)
}
export function applyRefund(data) {
  return request.post('/v1/user/payments/refund-apply/', data)
}
export function queryRefunds(params) {
  return request.get('/v1/user/payments/refund-query/', { params })
}
export function manualConfirm(data) {
  return request.post('/v1/user/payments/manual-confirm/', data)
}
export function getCashierOrder(orderNo, uin) {
  return request.get(`/v1/cashier/orders/${orderNo}/`, { params: { uin } })
}
export function payCashierOrder(orderNo, data) {
  return request.post(`/v1/cashier/orders/${orderNo}/pay/`, data)
}
