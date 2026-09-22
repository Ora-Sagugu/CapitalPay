export function recommendedPayoutCodes(data) {
  if (Array.isArray(data?.recommended_bank_codes) && data.recommended_bank_codes.length) {
    return data.recommended_bank_codes.filter(Boolean)
  }
  return data?.recommended_bank_code ? [data.recommended_bank_code] : []
}

export function confirmTransferPayload(codes) {
  const selected = (codes || []).filter(Boolean)
  if (selected.length > 1) return { bank_codes: selected }
  return { bank_code: selected[0] || '' }
}

export function payoutAmountNumber(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount : 0
}

export function splitPayoutLegs(banks, selectedCodes, payoutAmount) {
  const amount = payoutAmountNumber(payoutAmount)
  const selected = (selectedCodes || [])
    .map((code) => (banks || []).find((row) => row.bank_code === code))
    .filter(Boolean)
  if (selected.length === 1 && selected[0].sufficient) {
    return [{ ...selected[0], payout_amount: amount }]
  }
  if (selected.length !== 2 || amount <= 0) return []
  const leftover = selected.find((row) => {
    const balance = payoutAmountNumber(row.balance)
    return balance > 0 && balance < amount
  })
  const other = selected.find((row) => row !== leftover)
  if (!leftover || !other) return []
  const firstAmount = payoutAmountNumber(leftover.balance)
  const remainder = Number((amount - firstAmount).toFixed(2))
  if (payoutAmountNumber(other.balance) < remainder) return []
  return [
    { ...leftover, payout_amount: firstAmount },
    { ...other, payout_amount: remainder }
  ]
}

export function payoutSelectionComplete(banks, selectedCodes, payoutAmount) {
  const legs = splitPayoutLegs(banks, selectedCodes, payoutAmount)
  if ((selectedCodes || []).length === 1) return legs.length === 1
  return legs.length === 2
}

export function isPayoutBankDisabled(row, banks, selectedCodes, payoutAmount) {
  const selected = selectedCodes || []
  if (selected.includes(row.bank_code)) return false
  if (selected.length >= 2) return true
  if (selected.length === 0) return !row.selectable
  return splitPayoutLegs(banks, [...selected, row.bank_code], payoutAmount).length !== 2
}

export function payoutLegAmount(row, banks, selectedCodes, payoutAmount) {
  const legs = splitPayoutLegs(banks, selectedCodes, payoutAmount)
  const match = legs.find((leg) => leg.bank_code === row.bank_code)
  return match ? match.payout_amount : ''
}
