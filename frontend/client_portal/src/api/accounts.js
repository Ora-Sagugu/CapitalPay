import request from './request'

export function getVirtualAccounts(params) {
  return request.get('/v1/admin/virtual-accounts/', { params })
}
export function getFundTransfers(params) {
  return request.get('/v1/admin/fund-transfers/', { params })
}
export function getNostroAccounts(params) {
  return request.get('/v1/admin/nostro-accounts/', { params })
}
export function rechargeNostro(id, data) {
  return request.post(`/v1/admin/nostro-accounts/${id}/recharge/`, data)
}
export function getNostroTransactions(id) {
  return request.get(`/v1/admin/nostro-accounts/${id}/transactions/`)
}
export function getDeposits(params) {
  return request.get('/v1/admin/deposits/', { params })
}
export function reviewDeposit(depositNo, data) {
  return request.post(`/v1/admin/deposits/${depositNo}/review/`, data)
}
export function createDeposit(data) {
  return request.post('/v1/admin/deposits/', data)
}
export function getUserPaymentDetails(params) {
  return request.get('/v1/admin/user-payment-details/', { params })
}
