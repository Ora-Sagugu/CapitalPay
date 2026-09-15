import request from './request'

export function getVirtualAccounts(params) {
  return request.get('/v1/admin/virtual-accounts/', { params })
}
export function getVirtualAccountsByCustomer(params) {
  return request.get('/v1/admin/virtual-accounts/by-customer/', { params })
}
export function getVirtualAccountStats() {
  return request.get('/v1/admin/virtual-accounts/stats/')
}
export function getVaTransactions(id) {
  return request.get(`/v1/admin/virtual-accounts/${id}/transactions/`)
}
export function revokeVa(id, data) {
  return request.post(`/v1/admin/virtual-accounts/${id}/revoke/`, data)
}
export function getFundTransfers(params) {
  return request.get('/v1/admin/fund-transfers/', { params })
}
export function createFundTransfer(data) {
  return request.post('/v1/admin/fund-transfers/', data)
}
export function executeFundTransfer(transferNo) {
  return request.post(`/v1/admin/fund-transfers/${transferNo}/execute/`)
}
export function getNostroAccounts(params) {
  return request.get('/v1/admin/nostro-accounts/', { params })
}
export function getNostroStats() {
  return request.get('/v1/admin/nostro-accounts/stats/')
}
export function createNostroAccount(data) {
  return request.post('/v1/admin/nostro-accounts/', data)
}
export function updateNostroAccount(id, data) {
  return request.patch(`/v1/admin/nostro-accounts/${id}/`, data)
}
export function deleteNostroAccount(id) {
  return request.delete(`/v1/admin/nostro-accounts/${id}/`)
}
export function rechargeNostro(id, data) {
  return request.post(`/v1/admin/nostro-accounts/${id}/recharge/`, data)
}
export function deactivateNostro(id, data) {
  return request.post(`/v1/admin/nostro-accounts/${id}/deactivate/`, data)
}
export function getNostroTransactions(id) {
  return request.get(`/v1/admin/nostro-accounts/${id}/transactions/`)
}
export function getDeposits(params) {
  return request.get('/v1/admin/deposits/', { params })
}
export function getDepositStats() {
  return request.get('/v1/admin/deposits/stats/')
}
export function reviewDeposit(depositNo, data) {
  return request.post(`/v1/admin/deposits/${depositNo}/review/`, data)
}
export function createDeposit(data) {
  return request.post('/v1/admin/deposits/', data)
}
