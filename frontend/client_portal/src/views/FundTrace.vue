<template>
  <div>
    <PageHeader :title="$t('pages.fundTrace.title')" :subtitle="$t('pages.fundTrace.subtitle')" />
    <div class="page-card search-hero">
      <div class="search-row">
        <el-input
          v-model="keyword"
          size="large"
          :prefix-icon="Search"
          :placeholder="$t('pages.fundTrace.placeholder')"
          clearable
          @keyup.enter="search"
        />
        <el-button type="primary" size="large" :loading="loading" @click="search">
          {{ $t('pages.fundTrace.trace') }}
        </el-button>
      </div>
    </div>

    <EmptyState v-if="!order && !matches.length && !loading" :message="$t('pages.fundTrace.empty')" icon="🔎" />

    <div v-if="order" class="page-card">
      <div class="section-title">{{ $t('pages.fundTrace.orderInfo') }}</div>
      <el-descriptions :column="3" border>
        <el-descriptions-item :label="$t('pages.fundTrace.status')">
          <StatusPill :value="order.status" />
        </el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.orderNo')">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.merchantOrderNo')">{{ dash(order.merchant_order_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.merchant')">{{ dash(order.remitter_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.prn')">{{ dash(order.prn) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.amount')">{{ amountLabel(order) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.fee')">{{ moneyLabel(order.fee_amount, order.to_currency || order.from_currency) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.settledAmount')">{{ moneyLabel(order.settle_amount, order.to_currency || order.from_currency) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="order" class="next-banner">
      <div class="next-label">
        <el-icon><Promotion /></el-icon>
        {{ $t('pages.fundTrace.whereNext') }}
      </div>
      <div class="next-title">{{ nextTitle }}</div>
      <a class="next-link" @click.prevent="scrollToTarget">{{ nextLinkLabel }}</a>
      <div class="next-hint">{{ nextHint }}</div>
    </div>

    <div v-if="matches.length" id="beneficiary-section" class="page-card">
      <div class="section-head">
        <div class="section-title">{{ $t('pages.fundTrace.beneficiary') }}</div>
        <a class="new-search" @click.prevent="reset">{{ $t('pages.fundTrace.newSearch') }}</a>
      </div>
      <div class="match-hint">{{ $t('pages.fundTrace.foundMatches', { n: matchCount }) }}</div>
      <el-table :data="matches" :row-class-name="rowClass">
        <el-table-column prop="order_no" :label="$t('pages.fundTrace.orderNo')" min-width="190" />
        <el-table-column prop="beneficiary_name" :label="$t('pages.fundTrace.name')" min-width="140">
          <template #default="{ row }">{{ dash(row.beneficiary_name) }}</template>
        </el-table-column>
        <el-table-column prop="beneficiary_bank" :label="$t('pages.fundTrace.bank')" min-width="140">
          <template #default="{ row }">{{ dash(row.beneficiary_bank) }}</template>
        </el-table-column>
        <el-table-column :label="$t('pages.fundTrace.amount')" min-width="140">
          <template #default="{ row }">{{ moneyLabel(row.amount, row.to_currency || row.from_currency) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" width="120">
          <template #default="{ row }"><StatusPill :value="row.status" /></template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" round @click="pickOrder(row)">{{ $t('pages.fundTrace.trace') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="order" id="collection-va-section" class="page-card">
      <div class="va-title">
        <div class="section-title" style="margin: 0">{{ $t('pages.fundTrace.collectionVa') }}</div>
        <el-tag v-if="va?.va_type" type="info" size="small" effect="plain" round>{{ va.va_type }}</el-tag>
      </div>
      <el-descriptions v-if="va" :column="3" border style="margin-top: 12px">
        <el-descriptions-item :label="$t('pages.fundTrace.vaNumber')">{{ dash(va.va_number) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.bank')">{{ dash(va.bank_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.accountHolder')">{{ dash(va.account_holder) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('common.currency')">{{ dash(va.currency) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.ledgerBalance')">{{ moneyLabel(va.ledger_balance, va.currency) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.availableBalance')">{{ moneyLabel(va.available_balance, va.currency) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.routing')">{{ dash(va.routing_code) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('common.status')">{{ dash(va.status) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.masterAccount')">{{ dash(va.master_account_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('pages.fundTrace.masterBalance')">{{ moneyLabel(va.master_balance, va.currency) }}</el-descriptions-item>
      </el-descriptions>
      <div v-else class="match-hint" style="margin-top: 12px">{{ $t('pages.fundTrace.noVa') }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusPill from '@/components/StatusPill.vue'
import { traceFund } from '@/api/orders'
import { money } from '@/utils/format'

const { t, te } = useI18n()
const loading = ref(false)
const keyword = ref('')
const order = ref(null)
const matches = ref([])
const matchCount = ref(0)

const va = computed(() => order.value?.virtual_account || null)

const hopCode = computed(() => order.value?.next_hop?.code || '')
const hopTarget = computed(() => order.value?.next_hop?.target || 'beneficiary')

const nextTitle = computed(() => {
  const key = `pages.fundTrace.next.${hopCode.value}.title`
  return te(key) ? t(key) : ''
})
const nextHint = computed(() => {
  const key = `pages.fundTrace.next.${hopCode.value}.hint`
  return te(key) ? t(key) : ''
})
const nextLinkLabel = computed(() => {
  const key = `pages.fundTrace.nextTarget.${hopTarget.value}`
  const label = te(key) ? t(key) : t('pages.fundTrace.nextTarget.beneficiary')
  return `> ${label}`
})

function dash(v) {
  return v === null || v === undefined || v === '' ? '—' : v
}

function moneyLabel(amount, currency) {
  return `${money(amount)} ${currency || ''}`.trim()
}

function amountLabel(row) {
  const ccy = row.to_currency || row.from_currency || ''
  const pair = row.from_currency && row.to_currency ? ` (${row.from_currency} -> ${row.to_currency})` : ''
  return `${money(row.amount)} ${ccy}${pair}`
}

function rowClass({ row }) {
  return order.value && row.order_no === order.value.order_no ? 'is-current' : ''
}

async function load(selectedOrderNo) {
  const q = keyword.value.trim()
  if (!q) {
    ElMessage.warning(t('pages.fundTrace.keywordRequired'))
    return
  }
  loading.value = true
  try {
    const data = await traceFund({ q, selected_order_no: selectedOrderNo || undefined })
    matches.value = data.matches || []
    matchCount.value = data.match_count ?? matches.value.length
    order.value = data.order || null
  } catch {
    matches.value = []
    matchCount.value = 0
    order.value = null
  } finally {
    loading.value = false
  }
}

function search() {
  load()
}

function pickOrder(row) {
  load(row.order_no)
}

function reset() {
  keyword.value = ''
  order.value = null
  matches.value = []
  matchCount.value = 0
}

function scrollToTarget() {
  const target = hopTarget.value
  const id = target === 'collection_va' ? 'collection-va-section' : 'beneficiary-section'
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.search-hero { max-width: 860px; margin: 0 auto 24px; }
.search-row { display: flex; gap: 12px; align-items: center; }
.search-row :deep(.el-input) { flex: 1; }
.page-card { margin-bottom: 16px; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.section-head .section-title { margin: 0; }
.new-search {
  color: #4a90e2;
  cursor: pointer;
  font-size: 13px;
}
.match-hint {
  color: #8c8c8c;
  font-size: 13px;
  margin: 4px 0 12px;
}
.next-banner {
  background: #f3faf4;
  border: 1px solid #d8eedc;
  border-left: 4px solid #67c23a;
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 16px;
}
.next-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #67c23a;
  font-size: 13px;
  font-weight: 600;
}
.next-title {
  font-weight: 700;
  color: #2e7d32;
  margin: 8px 0 6px;
  font-size: 15px;
}
.next-link {
  color: #67c23a;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
}
.next-hint {
  color: #8c8c8c;
  font-size: 13px;
  margin-top: 6px;
}
.va-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
:deep(.is-current td) {
  background: #fdf6ef !important;
}
</style>
