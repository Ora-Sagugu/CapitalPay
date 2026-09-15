<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.accountTitle') }}</h1>
    <p class="psub">{{ $t('agent.accountSub') }}</p>

    <div class="page-card" v-loading="summaryLoading">
      <h2 class="section-heading">{{ $t('agent.accountTotals') }}</h2>
      <el-table v-if="totals.length" :data="totals">
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="140" />
        <el-table-column :label="$t('agent.accountBalance')" min-width="160">
          <template #default="{ row }">{{ money(row.balance) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!summaryLoading" :description="$t('agent.accountEmpty')" />
    </div>

    <div class="page-card">
      <h2 class="section-heading">{{ $t('agent.accountByCustomer') }}</h2>
      <el-table
        ref="customerTable"
        :data="customers"
        v-loading="customerLoading"
        row-key="merchant"
        @row-click="openDetail"
      >
        <el-table-column prop="merchant_name" :label="$t('agent.customerName')" min-width="180" />
        <el-table-column prop="merchant_no" :label="$t('agent.customerNo')" min-width="140" />
        <el-table-column :label="$t('agent.accountBalance')" min-width="220">
          <template #default="{ row }">{{ formatTotals(row.totals) }}</template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('common.status')" width="110" />
        <el-table-column :label="$t('common.actions')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">
              {{ $t('agent.accountView') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!customerLoading && !customers.length" :description="$t('agent.accountEmptyCustomers')" />
    </div>

    <div class="page-card">
      <h2 class="section-heading">{{ $t('agent.accountDeposits') }}</h2>
      <el-table :data="deposits" v-loading="depositLoading">
        <el-table-column prop="deposit_no" :label="$t('agent.accountDepositNo')" min-width="150" />
        <el-table-column prop="merchant_name" :label="$t('agent.customerName')" min-width="140" />
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="100" />
        <el-table-column :label="$t('common.amount')" min-width="120">
          <template #default="{ row }">{{ money(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('common.status')" width="120" />
        <el-table-column :label="$t('accounts.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!depositLoading && !deposits.length" :description="$t('agent.emptyDeposits')" />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="70%">
      <el-table :data="detailAccounts" v-loading="txLoading">
        <el-table-column prop="va_number" :label="$t('agent.vaNumber')" min-width="170" />
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="100" />
        <el-table-column :label="$t('accounts.balance')" min-width="120">
          <template #default="{ row }">{{ money(row.available_balance ?? row.balance) }}</template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('common.status')" width="110" />
        <el-table-column :label="$t('common.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLedger(row)">{{ $t('agent.accountLedger') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="ledgerVisible" :title="ledgerTitle" width="780px">
      <el-table :data="ledgerRows" v-loading="txLoading">
        <el-table-column :label="$t('accounts.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('accounts.direction')" min-width="110">
          <template #default="{ row }">{{ directionLabel(row.type || row.entry_type) }}</template>
        </el-table-column>
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="100" />
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">
            <span :class="isDebit(row) ? 'amt-out' : 'amt-in'">
              {{ signedAmount(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('accounts.balanceAfter')" min-width="140">
          <template #default="{ row }">{{ money(row.balance_after) }}</template>
        </el-table-column>
        <el-table-column prop="remark" :label="$t('wallet.remark')" min-width="180" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!txLoading && !ledgerRows.length" :description="$t('accounts.emptyLedger')" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import {
  getAgentAccounts,
  getAgentDeposits,
  getAgentVaTransactions,
  getAgentVirtualAccounts
} from '@/api/agent'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()

const summaryLoading = ref(false)
const customerLoading = ref(false)
const depositLoading = ref(false)
const txLoading = ref(false)
const totals = ref([])
const customers = ref([])
const deposits = ref([])
const customerTable = ref(null)

const detailVisible = ref(false)
const detail = ref(null)
const ledgerVisible = ref(false)
const ledgerRows = ref([])
const ledgerVa = ref(null)

const detailTitle = computed(() => {
  if (!detail.value) return t('agent.accountByCustomer')
  return `${detail.value.merchant_name} · ${detail.value.merchant_no}`
})
const detailAccounts = computed(() => detail.value?.accounts || [])
const ledgerTitle = computed(() => {
  if (!ledgerVa.value) return t('agent.accountLedger')
  return `${t('agent.accountLedger')} · ${ledgerVa.value.va_number || ''}`
})

function formatTotals(rows) {
  if (!rows?.length) return '—'
  return rows
    .map((row) => `${row.currency} ${money(row.available_balance ?? row.balance)}`)
    .join(' · ')
}

function directionLabel(type) {
  if (type === 'DEBIT') return t('accounts.debit')
  return t('accounts.credit')
}

function isDebit(row) {
  return (row.type || row.entry_type) === 'DEBIT'
}

function signedAmount(row) {
  const raw = String(row.amount ?? '0')
  if (raw.startsWith('-') || raw.startsWith('+')) return money(raw.replace(/^[+-]/, ''))
  const prefix = isDebit(row) ? '-' : '+'
  return `${prefix}${money(raw)}`
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

async function openLedger(row) {
  ledgerVa.value = row
  ledgerVisible.value = true
  ledgerRows.value = []
  txLoading.value = true
  try {
    const data = await getAgentVaTransactions(row.id)
    ledgerRows.value = data.transactions || data.items || []
  } finally {
    txLoading.value = false
  }
}

async function loadTotals() {
  if (auth.onboardingStatus !== 'approved') return
  summaryLoading.value = true
  try {
    const data = await getAgentAccounts()
    totals.value = data.items || []
  } finally {
    summaryLoading.value = false
  }
}

async function loadCustomers() {
  if (auth.onboardingStatus !== 'approved') return
  customerLoading.value = true
  try {
    const data = await getAgentVirtualAccounts({ page: 1, page_size: 100 })
    customers.value = data.results || []
    await nextTick()
    focusMerchantFromQuery()
  } finally {
    customerLoading.value = false
  }
}

async function loadDeposits() {
  if (auth.onboardingStatus !== 'approved') return
  depositLoading.value = true
  try {
    const data = await getAgentDeposits({ page: 1, page_size: 50 })
    deposits.value = data.items || []
  } finally {
    depositLoading.value = false
  }
}

function focusMerchantFromQuery() {
  const merchantId = String(route.query.merchant_id || '').trim()
  if (!merchantId) return
  const row = customers.value.find((item) => String(item.merchant) === merchantId)
  if (row) openDetail(row)
}

onMounted(() => {
  loadTotals()
  loadCustomers()
  loadDeposits()
})
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.page-card { background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.section-heading { margin: 0 0 16px; font-size: 16px; font-weight: 600; }
.amt-in { color: #67c23a; }
.amt-out { color: #f56c6c; }
</style>
