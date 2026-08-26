import request from './request'

// 合作银行
export function getCoopBanks(params) {
  return request.get('/v1/admin/coop-banks/', { params })
}
// 费率模型
export function getFeeModels(params) {
  return request.get('/v1/admin/fee-models/', { params })
}
// 银行费率配置
export function getBankFeeConfigs(params) {
  return request.get('/v1/admin/bank-fee-configs/', { params })
}
