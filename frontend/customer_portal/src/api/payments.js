import request from './request'

export function getPaymentHistory(params) {
  return request.get('/v1/user/payments/history/', { params })
}

export function getOrderDetail(orderNo) {
  return request.get('/v1/user/payments/order-detail/', { params: { order_no: orderNo } })
}
