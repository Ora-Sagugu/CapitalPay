import request from './request'

// 报表查询（POST query / export）
export function queryReport(path, params) {
  return request.post(`/v1/admin/reports/${path}/query/`, params)
}
export function exportReport(path, params) {
  return request.post(`/v1/admin/reports/${path}/export/`, params)
}

// 各类报表快捷方法
export const reportPaths = {
  remittance: 'remittance',
  merchantDaily: 'merchant-daily',
  channelFee: 'channel-fee',
  platformSummary: 'platform-summary',
  settleBatches: 'settle-batches',
  settleDetails: 'settle-details'
}
