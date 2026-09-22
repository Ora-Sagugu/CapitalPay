import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ENABLE_CARDS } from '@/config/features'
import {
  exhibitionCardInstruments,
  exhibitionCards,
  exhibitionCardTxns,
  exhibitionWallets,
  exhibitionWalletTxns,
  isExhibitionUser
} from '@/data/exhibitionFunding'
import {
  eventAmount,
  eventDirection,
  hasMoneyMovement,
  maskCard,
  normalizeCardBalance,
  normalizeCardEvent
} from '@/data/cardPlatform'

export function dec(v) {
  return Number(v || 0)
}

export function fmt(n) {
  return (Math.round(Number(n) * 100) / 100).toFixed(2)
}

export const WALLET_CREDIT_TYPES = new Set(['TOP_UP', 'TRANSFER_IN', 'UNFREEZE'])

export function addAmount(map, currency, amount) {
  const ccy = (currency || '').toUpperCase()
  if (!ccy) return
  map.set(ccy, fmt(dec(map.get(ccy) || 0) + dec(amount)))
}

export function mapToRows(map, valueKey = 'amount') {
  return Array.from(map.entries())
    .map(([currency, amount]) => ({ currency, [valueKey]: amount }))
    .sort((a, b) => a.currency.localeCompare(b.currency))
}

function cardEntryType(item) {
  return eventDirection(item) || 'DEBIT'
}

export const useFundingStore = defineStore('funding', () => {
  const wallets = ref([])
  const walletTxns = ref([])
  const cards = ref([])
  const cardTxns = ref([])
  const cardInstruments = ref([])

  const cardBalances = computed(() => cards.value.map(normalizeCardBalance))
  const cardEvents = computed(() => cardTxns.value.map(normalizeCardEvent))

  const walletAvailableRows = computed(() =>
    wallets.value.map((w) => ({ currency: w.currency, amount: w.available, status: w.status }))
  )

  const cardAvailableRows = computed(() =>
    cardBalances.value.map((c) => ({ currency: c.currency, amount: c.available, status: c.status }))
  )

  function spendableRows(bankBalances = []) {
    const map = new Map()
    for (const row of bankBalances || []) addAmount(map, row.currency, row.balance)
    for (const w of wallets.value) addAmount(map, w.currency, w.available)
    if (ENABLE_CARDS) {
      for (const c of cardBalances.value) addAmount(map, c.currency, c.available)
    }
    return mapToRows(map)
  }

  function hubActivity({ bankLedger = [] } = {}) {
    const rows = []
    for (const item of bankLedger) {
      rows.push({
        id: `bank-${item.id || item.created_at}`,
        rail: 'BANK',
        created_at: item.created_at,
        currency: item.currency,
        amount: item.amount,
        entry_type: item.entry_type || 'CREDIT',
        remark: item.remark || item.order_no || '',
        ref: item.order_no || '',
        demo: false
      })
    }
    for (const item of walletTxns.value) {
      rows.push({
        id: item.id,
        rail: 'WALLET',
        created_at: item.created_at,
        currency: item.currency,
        amount: item.amount,
        entry_type: WALLET_CREDIT_TYPES.has(item.type) ? 'CREDIT' : 'DEBIT',
        remark: item.remark,
        ref: item.id,
        demo: false
      })
    }
    if (ENABLE_CARDS) {
      for (const item of cardEvents.value) {
        if (!hasMoneyMovement(item)) continue
        rows.push({
          id: item.id,
          rail: 'CARD',
          created_at: item.occurred_at || item.created_at,
          currency: item.currency,
          amount: eventAmount(item),
          entry_type: cardEntryType(item),
          remark: item.remark || maskCard(item),
          ref: item.payment_id || item.id,
          demo: false
        })
      }
    }
    rows.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    return rows.slice(0, 20)
  }

  function ensureExhibitionFunding(user) {
    if (!isExhibitionUser(user)) return false
    if (!wallets.value.length) wallets.value = exhibitionWallets(user)
    if (!walletTxns.value.length) walletTxns.value = exhibitionWalletTxns(user)
    if (ENABLE_CARDS) {
      if (!cards.value.length) cards.value = exhibitionCards(user)
      if (!cardTxns.value.length) cardTxns.value = exhibitionCardTxns(user)
      if (!cardInstruments.value.length) cardInstruments.value = exhibitionCardInstruments(user)
    }
    return true
  }

  return {
    wallets,
    walletTxns,
    cards,
    cardTxns,
    cardInstruments,
    cardBalances,
    cardEvents,
    walletAvailableRows,
    cardAvailableRows,
    spendableRows,
    hubActivity,
    ensureExhibitionFunding
  }
})
