<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="ptitle">{{ $t('bank.title') }}</h1>
        <p class="psub">{{ $t('bank.subtitle') }}</p>
      </div>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      :title="$t('bank.recordHint')"
      class="record-alert"
    />

    <div class="page-card" v-loading="loading">
      <h2 class="section-heading">{{ $t('bank.details') }}</h2>
      <el-table v-if="accountCards.length" :data="accountCards">
        <el-table-column :label="$t('bank.source')" min-width="130">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column prop="bank_name" :label="$t('bank.bankName')" min-width="150" />
        <el-table-column prop="bank_code" :label="$t('bank.bankCode')" min-width="120" />
        <el-table-column prop="account_holder" :label="$t('bank.accountHolder')" min-width="160" />
        <el-table-column prop="account_number" :label="$t('bank.accountNumber')" min-width="140" />
        <el-table-column prop="swift_code" :label="$t('bank.swiftCode')" min-width="120">
          <template #default="{ row }">{{ row.swift_code || '—' }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" min-width="110">
          <template #default="{ row }">{{ row.status || '—' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" :description="$t('bank.emptyDetails')" />
    </div>

    <div class="page-card" v-loading="loading">
      <h2 class="section-heading">{{ $t('bank.balances') }}</h2>
      <el-table v-if="balanceRows.length" :data="balanceRows">
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="120" />
        <el-table-column :label="$t('bank.balance')" min-width="160">
          <template #default="{ row }">{{ money(row.balance) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" :description="$t('bank.emptyBalances')" />
    </div>

    <div class="page-card">
      <h2 class="section-heading">{{ $t('bank.ledger') }}</h2>
      <el-table
        v-if="ledger.length"
        :data="ledger"
        v-loading="ledgerLoading"
      >
        <el-table-column :label="$t('bank.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('bank.direction')" min-width="110">
          <template #default="{ row }">{{ directionLabel(row.entry_type) }}</template>
        </el-table-column>
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="100" />
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">
            <span :class="row.entry_type === 'DEBIT' ? 'amt-out' : 'amt-in'">
              {{ signedAmount(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('bank.balanceAfter')" min-width="140">
          <template #default="{ row }">{{ money(row.balance_after) }}</template>
        </el-table-column>
        <el-table-column :label="$t('bank.orderNo')" min-width="170">
          <template #default="{ row }">{{ row.order_no || '—' }}</template>
        </el-table-column>
        <el-table-column prop="remark" :label="$t('wallet.remark')" min-width="180" show-overflow-tooltip />
      </el-table>
      <el-empty v-else-if="!ledgerLoading" :description="$t('bank.emptyLedger')" />
    </div>

    <div class="page-card" v-loading="channelsLoading">
      <h2 class="section-heading">{{ $t('bank.channels') }}</h2>
      <el-table v-if="channels.length" :data="channels">
        <el-table-column prop="bank_name" :label="$t('bank.channelsBankName')" min-width="220" />
        <el-table-column prop="country" :label="$t('bank.country')" min-width="160">
          <template #default="{ row }">{{ row.country || '—' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!channelsLoading" :description="$t('bank.emptyChannels')" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { getAccountLedger, listBoundAccounts, listSupportedChannels } from '@/api/payments'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const loading = ref(false)
const ledgerLoading = ref(false)
const channelsLoading = ref(false)
const overview = ref({ registration: null, added_cards: [], balances: [] })
const ledger = ref([])
const channels = ref([])

const accountCards = computed(() => {
  const rows = []
  if (overview.value.registration) {
    rows.push({
      ...overview.value.registration,
      source: overview.value.registration.source || 'registration'
    })
  }
  for (const card of overview.value.added_cards || []) {
    rows.push({ ...card, source: card.source || 'added' })
  }
  return rows
})

const balanceRows = computed(() => {
  const topLevel = overview.value.balances || []
  if (topLevel.length) {
    return topLevel
      .map((row) => ({
        currency: (row.currency || '').toUpperCase(),
        balance: row.balance || '0.00'
      }))
      .filter((row) => row.currency)
      .sort((a, b) => a.currency.localeCompare(b.currency))
  }
  const byCurrency = new Map()
  for (const card of accountCards.value) {
    const balances = Array.isArray(card.balances) && card.balances.length
      ? card.balances
      : (card.currency ? [{ currency: card.currency, balance: card.balance || '0.00' }] : [])
    for (const row of balances) {
      const code = (row.currency || '').toUpperCase()
      if (!code) continue
      if (!byCurrency.has(code)) {
        byCurrency.set(code, { currency: code, balance: row.balance || '0.00' })
      }
    }
  }
  return Array.from(byCurrency.values()).sort((a, b) => a.currency.localeCompare(b.currency))
})

function sourceLabel(source) {
  if (source === 'registration') return t('bank.sourceRegistration')
  return t('bank.sourceAdded')
}

function directionLabel(type) {
  if (type === 'DEBIT') return t('bank.debit')
  return t('bank.credit')
}

function signedAmount(row) {
  const prefix = row.entry_type === 'DEBIT' ? '-' : '+'
  return `${prefix}${money(row.amount)}`
}

async function loadAccounts() {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    overview.value = await listBoundAccounts()
  } finally {
    loading.value = false
  }
}

async function loadLedger() {
  if (auth.onboardingStatus !== 'approved') return
  ledgerLoading.value = true
  try {
    const data = await getAccountLedger({ page: 1, page_size: 50 })
    ledger.value = data.items || []
  } finally {
    ledgerLoading.value = false
  }
}

async function loadChannels() {
  if (auth.onboardingStatus !== 'approved') return
  channelsLoading.value = true
  try {
    const data = await listSupportedChannels()
    channels.value = data.items || []
  } finally {
    channelsLoading.value = false
  }
}

onMounted(() => {
  loadAccounts()
  loadLedger()
  loadChannels()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.ptitle { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.record-alert { margin-bottom: 16px; }
.page-card { background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.section-heading { margin: 0 0 16px; font-size: 16px; font-weight: 600; }
.amt-in { color: #67c23a; }
.amt-out { color: #f56c6c; }
</style>
