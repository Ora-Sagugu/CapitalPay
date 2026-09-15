<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.earningsTitle') }}</h1>
    <p class="psub">{{ $t('agent.earningsSub') }}</p>

    <div class="toolbar">
      <el-radio-group v-model="period" size="default" @change="onPeriodChange">
        <el-radio-button value="week">{{ $t('agent.periodWeek') }}</el-radio-button>
        <el-radio-button value="month">{{ $t('agent.periodMonth') }}</el-radio-button>
        <el-radio-button value="quarter">{{ $t('agent.periodQuarter') }}</el-radio-button>
        <el-radio-button value="year">{{ $t('agent.periodYear') }}</el-radio-button>
        <el-radio-button value="all">{{ $t('agent.periodAll') }}</el-radio-button>
      </el-radio-group>
      <el-button v-if="merchantName" @click="clearMerchant">{{ $t('agent.clearCustomerFilter') }}</el-button>
    </div>
    <p v-if="periodLabel" class="period-range">{{ periodLabel }}</p>

    <div class="summary-grid" v-loading="loading">
      <div v-if="!summary.length" class="summary-card empty">
        <div class="summary-label">{{ $t('agent.totalAgentFee') }}</div>
        <div class="summary-value">{{ money(0) }}</div>
        <div class="summary-meta">{{ $t('agent.ordersCount', { n: 0 }) }}</div>
      </div>
      <div v-for="item in summary" :key="item.currency" class="summary-card">
        <div class="summary-label">{{ $t('agent.totalAgentFee') }} · {{ item.currency }}</div>
        <div class="summary-value">{{ money(item.agent_fee_total) }}</div>
        <div class="summary-meta">{{ $t('agent.ordersCount', { n: item.order_count }) }}</div>
      </div>
    </div>

    <div class="page-card">
      <div class="section-bar">
        <h2 class="section-heading">{{ $t('agent.byCustomerTitle') }}</h2>
        <span v-if="merchantName" class="filter-chip">
          {{ $t('agent.filteredCustomer', { name: merchantName }) }}
        </span>
      </div>
      <el-table
        :data="byCustomer"
        v-loading="loading"
        highlight-current-row
        @row-click="onCustomerRow"
      >
        <el-table-column prop="merchant_name" :label="$t('agent.customerName')" min-width="180" />
        <el-table-column prop="currency" :label="$t('common.currency')" width="100" />
        <el-table-column :label="$t('agent.agentFee')" min-width="140">
          <template #default="{ row }">{{ money(row.agent_fee_total) }}</template>
        </el-table-column>
        <el-table-column :label="$t('agent.orderCount')" width="120">
          <template #default="{ row }">{{ row.order_count }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !byCustomer.length" :description="$t('agent.emptyEarnings')" />
    </div>

    <div class="page-card">
      <div class="section-bar">
        <h2 class="section-heading">{{ $t('agent.detailTitle') }}</h2>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="order_no" :label="$t('orders.orderNo')" min-width="160" />
        <el-table-column prop="merchant_name" :label="$t('agent.customerName')" min-width="160" />
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">{{ money(row.amount) }} {{ row.currency }}</template>
        </el-table-column>
        <el-table-column :label="$t('agent.agentFee')" min-width="140">
          <template #default="{ row }">{{ money(row.agent_fee) }}</template>
        </el-table-column>
        <el-table-column :label="$t('orders.createdAt')" min-width="170">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.emptyEarnings')" />
      <el-pagination
        v-if="total > pageSize"
        class="pager"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { getAgentEarnings } from '@/api/agent'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const loading = ref(false)
const rows = ref([])
const summary = ref([])
const byCustomer = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const period = ref('month')
const merchantName = ref('')
const periodStart = ref(null)
const periodEnd = ref(null)

const periodLabel = computed(() => {
  if (!periodStart.value) {
    return period.value === 'all' ? t('agent.periodAllHint') : ''
  }
  const start = datetime(periodStart.value)
  const end = periodEnd.value ? datetime(periodEnd.value) : ''
  return t('agent.periodRange', { start, end })
})

async function load() {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize,
      period: period.value
    }
    if (merchantName.value) params.merchant_name = merchantName.value
    const data = await getAgentEarnings(params)
    rows.value = data.items || []
    total.value = data.total || 0
    summary.value = data.summary || []
    byCustomer.value = data.by_customer || []
    periodStart.value = data.period_start || null
    periodEnd.value = data.period_end || null
  } finally {
    loading.value = false
  }
}

function onPeriodChange() {
  page.value = 1
  load()
}

function onPage(p) {
  page.value = p
  load()
}

function onCustomerRow(row) {
  if (!row?.merchant_name) return
  merchantName.value = row.merchant_name
  page.value = 1
  load()
}

function clearMerchant() {
  merchantName.value = ''
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.period-range {
  margin: 0 0 14px;
  color: #8c8c8c;
  font-size: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
  min-height: 88px;
}
.summary-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.summary-card.empty { opacity: 0.85; }
.summary-label { color: #8c8c8c; font-size: 13px; margin-bottom: 8px; }
.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  letter-spacing: -0.02em;
}
.summary-meta { margin-top: 6px; color: #8c8c8c; font-size: 12px; }
.page-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.section-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.section-heading { margin: 0; font-size: 16px; font-weight: 600; }
.filter-chip {
  font-size: 12px;
  color: #c45a1a;
  background: #fff3e8;
  padding: 4px 10px;
  border-radius: 999px;
}
.pager { margin-top: 12px; }
</style>
