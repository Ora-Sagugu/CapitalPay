export function isAwaitingAgentPayout(row) {
  return row?.status === 'PAY_RECEIVED' && row?.agent_payout_request_status === 'pending'
}

export function canConfirmTransferStatus(row) {
  const gate = row?.agent_payout_request_status || 'none'
  if (gate === 'pending') return false
  if (gate === 'requested') return row.status === 'PAY_RECEIVED'
  return ['PENDING_PAY', 'PAY_RECEIVED'].includes(row.status)
}
