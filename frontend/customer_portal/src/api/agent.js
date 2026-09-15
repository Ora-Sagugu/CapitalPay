import request from './request'

export function getAgentProfile() {
  return request.get('/v1/user/agent/me/')
}

export function getAgentMerchants() {
  return request.get('/v1/user/agent/merchants/')
}

export function getAgentEarnings(params) {
  return request.get('/v1/user/agent/earnings/', { params })
}

export function getAgentKycList(params) {
  return request.get('/v1/user/agent/kyc/', { params })
}

export function getAgentKycDetail(userId) {
  return request.get(`/v1/user/agent/kyc/${userId}/`)
}

export function reviewAgentKyc(userId, data) {
  return request.post(`/v1/user/agent/kyc/${userId}/review/`, data)
}

export function getAgentOrders(params) {
  return request.get('/v1/user/agent/orders/', { params })
}

export function getAgentOrderDetail(orderNo) {
  return request.get(`/v1/user/agent/orders/${orderNo}/`)
}

export function reviewAgentOrder(orderNo, data) {
  return request.post(`/v1/user/agent/orders/${orderNo}/review/`, data)
}

export function requestAgentPayout(orderNo) {
  return request.post(`/v1/user/agent/orders/${orderNo}/request-payout/`)
}

export function getAgentFundTransferAccounts() {
  return request.get('/v1/user/agent/fund-transfers/accounts/')
}

export function getAgentFundTransfers(params) {
  return request.get('/v1/user/agent/fund-transfers/', { params })
}

export function createAgentFundTransfer(data) {
  return request.post('/v1/user/agent/fund-transfers/', data)
}

export function executeAgentFundTransfer(transferNo) {
  return request.post(`/v1/user/agent/fund-transfers/${transferNo}/execute/`)
}

export function getAgentAccounts() {
  return request.get('/v1/user/agent/accounts/')
}

export function getAgentAccountCurrencies() {
  return request.get('/v1/user/agent/accounts/currencies/')
}

export function enableAgentAccountCurrency(currency) {
  return request.post('/v1/user/agent/accounts/enable/', { currency })
}

export function getAgentDeposits(params) {
  return request.get('/v1/user/agent/accounts/deposits/', { params })
}

export function createAgentDeposit(data) {
  return request.post('/v1/user/agent/accounts/deposits/', data)
}

export function getAgentVirtualAccounts(params) {
  return request.get('/v1/user/agent/virtual-accounts/', { params })
}

export function getAgentVaTransactions(vaId) {
  return request.get(`/v1/user/agent/virtual-accounts/${vaId}/transactions/`)
}

export function agentRemittanceQuote(data) {
  return request.post('/v1/user/agent/payments/quote/', data)
}

export function agentRemittanceApply(data, idempotencyKey) {
  return request.post('/v1/user/agent/payments/apply/', data, {
    headers: { 'Idempotency-Key': idempotencyKey }
  })
}

export function agentSanctionCheck(data) {
  return request.post('/v1/user/agent/payments/sanction-check/', data)
}
