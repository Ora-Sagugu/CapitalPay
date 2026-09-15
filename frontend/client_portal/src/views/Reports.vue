<template>
  <div>
    <PageHeader :title="$t('pages.reports.title')" :subtitle="$t('pages.reports.subtitle')" />
    <el-alert type="warning" :closable="false" show-icon class="caveat">
      {{ $t('pages.reports.caveat') }}
    </el-alert>

    <div class="page-card toolbar-card">
      <div class="toolbar">
        <el-date-picker
          v-model="filters.range"
          type="daterange"
          value-format="YYYY-MM-DD"
          :start-placeholder="$t('pages.reports.startDate')"
          :end-placeholder="$t('pages.reports.endDate')"
          style="width: 260px"
        />
        <el-select v-model="filters.time_basis" style="width: 160px">
          <el-option :label="$t('pages.reports.basisCreated')" value="created_at" />
          <el-option :label="$t('pages.reports.basisReceived')" value="pay_received_at" />
          <el-option :label="$t('pages.reports.basisRefunded')" value="refunded_at" />
          <el-option :label="$t('pages.reports.basisSettled')" value="settled_at" />
        </el-select>
        <el-select v-if="ENABLE_AGENTS" v-model="filters.agent_id" :placeholder="$t('pages.reports.allAgents')" clearable filterable style="width: 180px">
          <el-option v-for="a in agents" :key="a.id" :label="a.agent_name" :value="a.id" />
        </el-select>
        <el-select v-model="filters.merchant_id" :placeholder="$t('pages.reports.allMerchants')" clearable filterable style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.merchant_name" :value="m.id" />
        </el-select>
        <el-input v-model="filters.user_id" :placeholder="$t('pages.reports.userId')" clearable style="width: 140px" />
        <el-input v-model="filters.from_currency" :placeholder="$t('pages.reports.fromCurrency')" clearable style="width: 110px" />
        <el-input v-model="filters.order_no" :placeholder="$t('pages.reports.orderNo')" clearable style="width: 180px" />
        <el-button type="primary" data-test="query-analytics" :loading="loading" @click="loadAnalytics">{{ $t('common.search') }}</el-button>
        <el-button v-if="canExport" type="success" data-test="export-analytics" @click="exportExcel">{{ $t('pages.reports.export') }}</el-button>
      </div>
    </div>

    <el-tabs v-model="tab" @tab-change="onTabChange">
      <el-tab-pane :label="$t('pages.reports.tabOverview')" name="overview" />
      <el-tab-pane :label="$t('pages.reports.tabBreakdown')" name="breakdown" />
      <el-tab-pane :label="$t('pages.reports.tabTransactions')" name="transactions" />
      <el-tab-pane :label="$t('pages.reports.tabLegacy')" name="legacy" />
    </el-tabs>

    <div v-if="tab === 'overview'">
      <div class="kpi-grid" data-test="kpi-grid">
        <div class="kpi-block">
          <div class="kpi-title">{{ $t('pages.reports.application') }}</div>
          <div class="kpi-count">{{ summary.application?.count ?? 0 }}</div>
          <div v-for="row in summary.application?.by_currency || []" :key="'a'+row.currency" class="kpi-ccy">
            {{ row.currency || '—' }} {{ money(row.amount) }} / {{ row.count }}
          </div>
        </div>
        <div class="kpi-block">
          <div class="kpi-title">{{ $t('pages.reports.confirmed') }}</div>
          <div class="kpi-count">{{ summary.confirmed_collection?.count ?? 0 }}</div>
          <div v-for="row in summary.confirmed_collection?.by_currency || []" :key="'c'+row.currency" class="kpi-ccy">
            {{ row.currency || '—' }} {{ money(row.amount) }} / {{ row.count }}
          </div>
        </div>
        <div class="kpi-block">
          <div class="kpi-title">{{ $t('pages.reports.refunds') }}</div>
          <div class="kpi-count">{{ summary.successful_refunds?.count ?? 0 }}</div>
          <div v-for="row in summary.successful_refunds?.by_currency || []" :key="'r'+row.currency" class="kpi-ccy">
            {{ row.currency || '—' }} {{ money(row.amount) }} / {{ row.count }}
          </div>
        </div>
        <div class="kpi-block">
          <div class="kpi-title">{{ $t('pages.reports.pending') }}</div>
          <div class="kpi-count">{{ pendingTotal }}</div>
          <div class="kpi-ccy">{{ $t('pages.reports.pendingReview') }} {{ summary.pending?.review?.count ?? 0 }}</div>
          <div class="kpi-ccy">{{ $t('pages.reports.pendingPay') }} {{ summary.pending?.pay?.count ?? 0 }}</div>
          <div class="kpi-ccy">{{ $t('pages.reports.pendingSettle') }} {{ summary.pending?.settle?.count ?? 0 }}</div>
        </div>
      </div>
      <div class="page-card">
        <div class="section-title">{{ $t('pages.reports.trend') }}</div>
        <div ref="chartRef" data-test="trend-chart" style="height: 320px" />
      </div>
      <div class="page-card">
        <div class="section-title">{{ $t('pages.reports.funnel') }}</div>
        <el-table :data="summary.funnel || []">
          <el-table-column prop="label" :label="$t('pages.reports.step')" />
          <el-table-column prop="count" :label="$t('pages.reports.count')" width="120" />
        </el-table>
      </div>
      <div class="page-card">
        <div class="section-title">{{ $t('pages.reports.feeShare') }}</div>
        <EmptyState v-if="!(summary.fee_share_estimated?.by_currency || []).length" :message="$t('pages.reports.noFeeShare')" />
        <el-table v-else :data="summary.fee_share_estimated.by_currency">
          <el-table-column prop="currency" :label="$t('common.currency')" min-width="110" />
          <el-table-column v-if="ENABLE_BANKING" prop="channel_fee" :label="$t('pages.reports.channelFee')" :formatter="moneyCol" />
          <el-table-column prop="platform_fee" :label="$t('pages.reports.platformFee')" :formatter="moneyCol" />
          <el-table-column v-if="ENABLE_AGENTS" prop="agent_fee" :label="$t('pages.reports.agentFee')" :formatter="moneyCol" />
        </el-table>
      </div>
    </div>

    <div v-else-if="tab === 'breakdown'" class="page-card">
      <div class="toolbar">
        <el-select v-model="filters.dimension" style="width: 180px" @change="loadBreakdown">
          <el-option :label="$t('pages.reports.dimMerchant')" value="merchant" />
          <el-option :label="$t('pages.reports.dimUser')" value="user" />
          <el-option v-if="ENABLE_AGENTS" :label="$t('pages.reports.dimAgent')" value="agent" />
          <el-option v-if="ENABLE_BANKING" :label="$t('pages.reports.dimChannel')" value="channel" />
          <el-option :label="$t('pages.reports.dimStatus')" value="status" />
          <el-option :label="$t('pages.reports.dimCurrency')" value="currency" />
        </el-select>
        <span class="coverage">{{ $t('pages.reports.coverage', { rate: breakdown.coverage?.user_id?.rate || breakdown.coverage?.rate || '—' }) }}</span>
      </div>
      <EmptyState v-if="!(breakdown.rows || []).length" :message="$t('pages.reports.empty')" />
      <el-table v-else :data="breakdown.rows" @row-click="drilldown">
        <el-table-column prop="label" :label="$t('pages.reports.dimension')" min-width="180">
          <template #default="{ row }">
            {{ row.label }}
            <el-tag v-if="row.unlinked" size="small" type="info">{{ $t('pages.reports.unlinked') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="count" :label="$t('pages.reports.count')" width="100" />
        <el-table-column :label="$t('pages.reports.byCurrency')" min-width="260">
          <template #default="{ row }">
            <span v-for="c in row.by_currency" :key="c.currency" class="ccy-chip">
              {{ c.currency || '—' }} {{ money(c.amount) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else-if="tab === 'transactions'" class="page-card">
      <EmptyState v-if="!(transactions.results || []).length" :message="$t('pages.reports.empty')" />
      <el-table v-else :data="transactions.results">
        <el-table-column prop="order_no" :label="$t('pages.reports.orderNo')" min-width="180" />
        <el-table-column prop="merchant_name" :label="$t('pages.reports.merchant')" min-width="140" />
        <el-table-column prop="user_id" :label="$t('pages.reports.userId')" width="120">
          <template #default="{ row }">{{ row?.user_linked ? row.user_id : $t('pages.reports.unlinked') }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">{{ row?.from_currency }} {{ money(row?.amount) }}</template>
        </el-table-column>
        <el-table-column :label="$t('pages.reports.fee')" width="120">
          <template #default="{ row }">{{ money(row?.fee_amount) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" width="120">
          <template #default="{ row }"><StatusPill :value="row?.status" /></template>
        </el-table-column>
        <el-table-column prop="beneficiary_account" :label="$t('pages.reports.beneficiaryAccount')" min-width="140" />
        <el-table-column :label="$t('common.actions')" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link data-test="trace-btn" @click="openTrace(row?.order_no)">{{ $t('pages.reports.trace') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="transactions.count"
        class="pager"
        background
        layout="total, prev, pager, next"
        :page-size="filters.page_size"
        :current-page="filters.page"
        :total="transactions.count"
        @current-change="onPage"
      />
    </div>

    <div v-else class="page-card">
      <div class="toolbar">
        <el-select v-model="reportType" style="width: 180px">
          <el-option :label="$t('pages.reports.legacyRemittance')" value="remittance" />
          <el-option :label="$t('pages.reports.legacyDaily')" value="merchant-daily" />
          <el-option v-if="ENABLE_BANKING" :label="$t('pages.reports.legacyChannel')" value="channel-fee" />
          <el-option :label="$t('pages.reports.legacySummary')" value="platform-summary" />
          <el-option :label="$t('pages.reports.legacyBatches')" value="settle-batches" />
          <el-option :label="$t('pages.reports.legacyDetails')" value="settle-details" />
        </el-select>
        <el-button type="primary" @click="queryLegacy">{{ $t('common.search') }}</el-button>
        <el-button v-if="canExport" type="success" @click="exportLegacy">{{ $t('pages.reports.export') }}</el-button>
        <el-button v-if="reportType !== 'remittance' && canExport" @click="generateNow">{{ $t('pages.reports.generate') }}</el-button>
      </div>
      <EmptyState v-if="!legacyRows.length" :message="$t('pages.reports.emptyLegacy')" />
      <el-table v-else :data="legacyRows">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column v-for="col in legacyColumns" :key="col.prop" :prop="col.prop" :label="col.label" min-width="140" :formatter="col.formatter" />
      </el-table>
    </div>

    <el-drawer v-model="traceOpen" :title="$t('pages.reports.traceTitle')" size="520px">
      <div v-if="trace" data-test="trace-drawer">
        <el-timeline>
          <el-timeline-item
            v-for="step in trace.timeline || []"
            :key="step.code"
            :type="step.verified ? 'success' : 'warning'"
          >
            <div>{{ step.title }}</div>
            <div class="hint">{{ step.at || '—' }}</div>
            <el-tag v-if="!step.verified" size="small" type="warning">{{ $t('pages.reports.unverified') }}</el-tag>
          </el-timeline-item>
        </el-timeline>
        <div class="section-title">{{ $t('pages.reports.movements') }}</div>
        <el-table :data="trace.money_movements || []" size="small">
          <el-table-column prop="movement_type" :label="$t('pages.reports.type')" width="140" />
          <el-table-column :label="$t('common.amount')">
            <template #default="{ row }">{{ row?.currency }} {{ money(row?.amount) }}</template>
          </el-table-column>
          <el-table-column prop="evidence_level" :label="$t('pages.reports.evidence')" width="140" />
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useAuthStore } from '@/store/auth'
import { getAgents } from '@/api/agents'
import { getMerchants } from '@/api/merchants'
import { ENABLE_AGENTS, ENABLE_BANKING } from '@/config/features'
import {
  queryReport, exportReport, generateReport,
  getAnalyticsSummary, getAnalyticsTrend, getAnalyticsBreakdowns,
  getAnalyticsTransactions, getAnalyticsTrace, exportAnalytics
} from '@/api/report'
import { unwrapList, isMoneyField, formatMoneyCell, money } from '@/utils/format'

const auth = useAuthStore()
const canExport = computed(() => auth.hasPermission('feature:reports'))

const tab = ref('overview')
const loading = ref(false)
const chartRef = ref(null)
let chart = null

const defaultRange = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 6)
  const fmt = (d) => d.toISOString().slice(0, 10)
  return [fmt(start), fmt(end)]
}

const filters = reactive({
  range: defaultRange(),
  time_basis: 'created_at',
  agent_id: '',
  merchant_id: '',
  user_id: '',
  from_currency: '',
  order_no: '',
  status: '',
  dimension: 'merchant',
  page: 1,
  page_size: 20
})
const agents = ref([])
const merchants = ref([])
const summary = ref({})
const trend = ref({ series: [] })
const breakdown = ref({ rows: [] })
const transactions = ref({ results: [], count: 0 })
const traceOpen = ref(false)
const trace = ref(null)
const reportType = ref('remittance')
const legacyRows = ref([])
const legacyColumns = ref([])

const pendingTotal = computed(() => (
  (summary.value.pending?.review?.count || 0)
  + (summary.value.pending?.pay?.count || 0)
  + (summary.value.pending?.settle?.count || 0)
))

function moneyCol(_row, _col, value) {
  return money(value)
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const series = trend.value.series || []
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['Count', 'Amount'] },
    grid: { left: 48, right: 48, top: 32, bottom: 32 },
    xAxis: { type: 'category', data: series.map((d) => d.date) },
    yAxis: [
      { type: 'value', name: 'Count' },
      { type: 'value', name: 'Amount', splitLine: { show: false } }
    ],
    series: [
      { name: 'Count', type: 'bar', data: series.map((d) => d.application_count) },
      { name: 'Amount', type: 'line', yAxisIndex: 1, data: series.map((d) => Number((d.by_currency || [])[0]?.application_amount || 0)) }
    ]
  }, true)
}

async function loadAnalytics() {
  if (!filters.range?.length) {
    ElMessage.warning('Select a date range.')
    return
  }
  loading.value = true
  try {
    summary.value = await getAnalyticsSummary(filters)
    trend.value = await getAnalyticsTrend(filters)
    if (tab.value === 'overview') renderChart()
    if (tab.value === 'breakdown') await loadBreakdown()
    if (tab.value === 'transactions') await loadTransactions()
  } finally {
    loading.value = false
  }
}

async function loadBreakdown() {
  breakdown.value = await getAnalyticsBreakdowns(filters)
}

async function loadTransactions() {
  transactions.value = await getAnalyticsTransactions(filters)
}

function onTabChange(name) {
  if (name === 'breakdown') loadBreakdown()
  if (name === 'transactions') loadTransactions()
  if (name === 'overview') setTimeout(renderChart, 0)
}

function drilldown(row) {
  if (filters.dimension === 'merchant') filters.merchant_id = row.key
  if (filters.dimension === 'user' && !row.unlinked) filters.user_id = row.key
  if (filters.dimension === 'agent' && !row.unlinked) filters.agent_id = row.key
  if (filters.dimension === 'status') filters.status = row.key
  if (filters.dimension === 'currency') filters.from_currency = row.key
  tab.value = 'transactions'
  filters.page = 1
  loadTransactions()
}

function onPage(page) {
  filters.page = page
  loadTransactions()
}

async function openTrace(orderNo) {
  trace.value = await getAnalyticsTrace(orderNo)
  traceOpen.value = true
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportExcel() {
  const blob = await exportAnalytics(filters)
  downloadBlob(blob, 'payment-analytics.xlsx')
  ElMessage.success('Export completed.')
}

function legacyParams() {
  const [date_from, date_to] = filters.range || []
  const merchant = merchants.value.find((m) => m.id === filters.merchant_id)
  const agent = ENABLE_AGENTS ? agents.value.find((a) => a.id === filters.agent_id) : null
  return {
    date_from,
    date_to,
    merchant_name: merchant?.merchant_name,
    agent_name: agent?.agent_name
  }
}

async function queryLegacy() {
  const data = await queryReport(reportType.value, legacyParams())
  const list = data.results || data.items || data.rows || data.orders || []
  legacyRows.value = list
  const first = list[0]
  legacyColumns.value = first ? Object.keys(first).map((k) => ({
    prop: k,
    label: k,
    formatter: isMoneyField(k) ? formatMoneyCell : undefined
  })) : []
}

async function exportLegacy() {
  const blob = await exportReport(reportType.value, legacyParams())
  downloadBlob(blob, `${reportType.value}-report.xlsx`)
  ElMessage.success('Export completed.')
}

async function generateNow() {
  const [date_from] = filters.range || []
  await generateReport(reportType.value, { report_date: date_from })
  ElMessage.success('Generation completed.')
  queryLegacy()
}

function resize() { chart && chart.resize() }

onMounted(async () => {
  if (ENABLE_AGENTS) {
    agents.value = unwrapList(await getAgents({ page_size: 100 })).rows
  }
  merchants.value = unwrapList(await getMerchants({ page_size: 100 })).rows
  await loadAnalytics()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
</script>

<style scoped>
.caveat { margin-bottom: 12px; }
.toolbar-card { margin-bottom: 12px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px; }
.kpi-block { background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
.kpi-title { color: #8c8c8c; font-size: 13px; }
.kpi-count { font-size: 26px; font-weight: 700; margin: 6px 0; }
.kpi-ccy { color: #606266; font-size: 12px; }
.ccy-chip { margin-right: 8px; }
.coverage { color: #909399; font-size: 13px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.hint { color: #909399; font-size: 12px; }
.section-title { font-weight: 600; margin-bottom: 8px; }
</style>
