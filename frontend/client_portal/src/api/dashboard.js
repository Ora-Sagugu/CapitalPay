import request from './request'

// 仪表盘统计：GET /api/v1/admin/orders/stats/
// 返回: { pending_review, pending_pay, completed_count, today_amount }
export function getOrderStats() {
  return request.get('/v1/admin/orders/stats/')
}
