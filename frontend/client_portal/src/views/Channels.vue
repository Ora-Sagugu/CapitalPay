<template>
  <div>
    <PageHeader title="Channels" subtitle="Bank accounts, balances and remittance channels">
      <el-button type="primary" @click="openCreate">+ Create</el-button>
    </PageHeader>
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="search" placeholder="Search by bank name" clearable style="width: 220px" @keyup.enter="load" />
        <el-button @click="load">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" class="banks-table" style="width: 100%" table-layout="fixed">
        <el-table-column prop="bank_name" label="Bank Name" min-width="180" show-overflow-tooltip />
        <el-table-column prop="bank_code" label="Bank Code" min-width="120" show-overflow-tooltip />
        <el-table-column prop="country" label="Country" min-width="160" />
        <el-table-column label="Fee Rule" min-width="160">
          <template #default="{ row }">{{ feeRuleText(row.fee_rate) }}</template>
        </el-table-column>
        <el-table-column label="Balances" min-width="160">
          <template #default="{ row }">{{ balancesText(row) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">Details</el-button>
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-drawer v-model="detailVisible" :title="detailTitle" size="640px">
      <div v-loading="detailLoading">
        <el-descriptions title="Identity" :column="1" border>
          <el-descriptions-item label="Bank Code">{{ dash(detail.bank_code) }}</el-descriptions-item>
          <el-descriptions-item label="Bank name">{{ dash(detail.bank_name) }}</el-descriptions-item>
          <el-descriptions-item label="Country">{{ dash(detail.country) }}</el-descriptions-item>
          <el-descriptions-item label="Channel type">{{ channelTypeLabel(detail.channel_type) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Balances" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="USD">{{ money(detail.usd_balance) }}</el-descriptions-item>
          <el-descriptions-item label="HKD">{{ money(detail.hkd_balance) }}</el-descriptions-item>
          <el-descriptions-item label="CNY">{{ money(detail.cny_balance) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Fees & limits" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="Fee Rule">{{ feeRuleText(detail.fee_rate) }}</el-descriptions-item>
          <el-descriptions-item label="Min fee">{{ money(detail.min_fee) }}</el-descriptions-item>
          <el-descriptions-item label="Max fee">{{ money(detail.max_fee) }}</el-descriptions-item>
          <el-descriptions-item label="Daily limit">{{ money(detail.daily_limit) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Capacity" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="Priority">{{ dash(detail.priority) }}</el-descriptions-item>
          <el-descriptions-item label="Success rate">{{ dash(detail.success_rate) }}</el-descriptions-item>
          <el-descriptions-item label="Avg response time">{{ responseTime(detail.avg_response_time) }}</el-descriptions-item>
          <el-descriptions-item label="Supported currencies">{{ listText(detail.supported_currencies) }}</el-descriptions-item>
          <el-descriptions-item label="Supported countries">{{ listText(detail.supported_countries) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Ops" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="API endpoint">{{ dash(detail.api_endpoint) }}</el-descriptions-item>
          <el-descriptions-item label="Health check URL">{{ dash(detail.health_check_url) }}</el-descriptions-item>
          <el-descriptions-item label="Remark">{{ dash(detail.remark) }}</el-descriptions-item>
          <el-descriptions-item label="Created">{{ datetime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="Updated">{{ datetime(detail.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="txn-title">Recent remittances</h4>
        <el-table :data="txns" v-loading="txnLoading">
          <el-table-column prop="prn" label="PRN" min-width="140" />
          <el-table-column prop="beneficiary_name" label="Beneficiary" min-width="140" />
          <el-table-column prop="amount" label="Amount" min-width="110" :formatter="formatMoneyCell" />
          <el-table-column prop="currency" label="Currency" width="90" />
          <el-table-column prop="fee" label="Fee" min-width="90" :formatter="formatMoneyCell" />
          <el-table-column label="Date/time" min-width="160">
            <template #default="{ row }">{{ datetime(row.txn_date) }}</template>
          </el-table-column>
          <template #empty><EmptyState message="No remittance records" /></template>
        </el-table>
      </div>
    </el-drawer>
    <el-dialog v-model="visible" :title="form.id ? 'Edit channel' : 'Create channel'" width="520px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="Bank Code"><el-input v-model="form.bank_code" /></el-form-item>
        <el-form-item label="Bank name"><el-input v-model="form.bank_name" /></el-form-item>
        <el-form-item label="Country"><el-input v-model="form.country" /></el-form-item>
        <el-form-item label="Fee rate"><el-input v-model="form.fee_rate" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import EmptyState from '@/components/EmptyState.vue'
import { getChannels, getChannel, getChannelStats, getChannelTransactions, createChannel, updateChannel } from '@/api/routing'
import { unwrapList, money, formatMoneyCell, datetime } from '@/utils/format'

const CHANNEL_TYPE = {
  online: 'Online banking',
  wire: 'Wire transfer',
  ach: 'ACH',
  realtime: 'Realtime'
}

const rows = ref([])
const stats = ref({})
const loading = ref(false)
const search = ref('')
const visible = ref(false)
const form = reactive({ id: '', bank_code: '', bank_name: '', country: '', fee_rate: '0.001' })
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = reactive({})
const txns = ref([])
const txnLoading = ref(false)
const kpis = computed(() => [
  { label: 'Banks', value: stats.value.total_channels ?? 0 },
  { label: 'Remittance volume', value: stats.value.total_txn_count ?? 0 },
  { label: 'USD nostro pool', value: money(stats.value.total_usd) }
])
const detailTitle = computed(() => detail.bank_name || 'Channel details')

function dash(value) {
  if (value === null || value === undefined || value === '') return '—'
  return value
}
function feeRuleText(rate) {
  if (rate === null || rate === undefined || rate === '') return '—'
  const n = Number(rate)
  if (Number.isNaN(n)) return '—'
  const pct = n * 100
  const formatted = pct.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4
  })
  return `${formatted}%`
}
function listText(value) {
  if (!value || (Array.isArray(value) && !value.length)) return '—'
  return Array.isArray(value) ? value.join(', ') : String(value)
}
function channelTypeLabel(code) {
  if (!code) return '—'
  return CHANNEL_TYPE[code] || code
}
function responseTime(ms) {
  if (ms === null || ms === undefined || ms === '') return '—'
  return `${ms} ms`
}
function compactAmount(n) {
  if (Number.isInteger(n) || n % 1 === 0) return String(Math.round(n))
  return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}
function balancesText(row) {
  const parts = []
  for (const [prefix, key] of [['$', 'usd_balance'], ['HK$', 'hkd_balance'], ['¥', 'cny_balance']]) {
    const n = Number(row?.[key])
    if (!Number.isNaN(n) && n !== 0) parts.push(`${prefix}${compactAmount(n)}`)
  }
  return parts.length ? parts.join(' · ') : '—'
}

async function load() {
  loading.value = true
  try {
    stats.value = await getChannelStats()
    const data = await getChannels({ search: search.value || undefined, page_size: 50 })
    rows.value = unwrapList(data).rows
  } finally { loading.value = false }
}
function openCreate() { Object.assign(form, { id: '', bank_code: '', bank_name: '', country: '', fee_rate: '0.001' }); visible.value = true }
function openEdit(row) { Object.assign(form, row); visible.value = true }
async function openDetail(row) {
  Object.keys(detail).forEach((key) => { delete detail[key] })
  Object.assign(detail, row || {})
  txns.value = []
  detailVisible.value = true
  detailLoading.value = true
  txnLoading.value = true
  try {
    const [channel, txnData] = await Promise.all([
      getChannel(row.id),
      getChannelTransactions(row.id, { page_size: 20 })
    ])
    Object.assign(detail, channel || {})
    txns.value = unwrapList(txnData).rows
  } finally {
    detailLoading.value = false
    txnLoading.value = false
  }
}
async function save() {
  const payload = {
    bank_code: form.bank_code,
    bank_name: form.bank_name,
    country: form.country,
    fee_rate: form.fee_rate
  }
  if (form.id) await updateChannel(form.id, payload)
  else await createChannel(payload)
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}
onMounted(load)
</script>

<style scoped>
.txn-title {
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
}
.banks-table :deep(.el-table__header .cell),
.banks-table :deep(.el-table__body .cell) {
  padding-left: 16px;
  padding-right: 16px;
}
.banks-table :deep(.el-table__header th:first-child .cell),
.banks-table :deep(.el-table__body td:first-child .cell) {
  padding-left: 8px;
}
.banks-table :deep(.el-table__header th:last-child .cell),
.banks-table :deep(.el-table__body td:last-child .cell) {
  padding-right: 8px;
}
</style>
