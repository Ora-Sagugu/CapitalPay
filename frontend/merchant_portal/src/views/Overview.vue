<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="ptitle">{{ $t('overview.title') }}</h1>
        <p class="psub">{{ $t('overview.subtitle') }}</p>
      </div>
      <el-radio-group v-model="period" @change="load">
        <el-radio-button value="day">{{ $t('overview.periodDay') }}</el-radio-button>
        <el-radio-button value="month">{{ $t('overview.periodMonth') }}</el-radio-button>
        <el-radio-button value="all">{{ $t('overview.periodAll') }}</el-radio-button>
      </el-radio-group>
    </div>

    <div class="kpi-grid" v-loading="loading">
      <div class="page-card kpi-card" data-testid="kpi-count">
        <h2 class="kpi-label">{{ $t('overview.remittanceCount') }}</h2>
        <p class="kpi-value">{{ stats.remittance_count ?? 0 }}</p>
      </div>
      <div class="page-card kpi-card" data-testid="kpi-amount">
        <h2 class="kpi-label">{{ $t('overview.totalAmount') }}</h2>
        <template v-if="stats.by_currency?.length">
          <p v-for="row in stats.by_currency" :key="`amt-${row.currency}`" class="kpi-value multi">
            {{ money(row.total_amount) }} <span class="ccy">{{ row.currency }}</span>
          </p>
        </template>
        <p v-else class="kpi-value">{{ money(0) }}</p>
      </div>
      <div class="page-card kpi-card" data-testid="kpi-success">
        <h2 class="kpi-label">{{ $t('overview.successRate') }}</h2>
        <p class="kpi-value">{{ formatRate(stats.success_rate) }}</p>
        <p class="kpi-hint">{{ $t('overview.successHint', { success: stats.success_count ?? 0, total: stats.remittance_count ?? 0 }) }}</p>
      </div>
      <div class="page-card kpi-card" data-testid="kpi-fee">
        <h2 class="kpi-label">{{ $t('overview.totalFee') }}</h2>
        <template v-if="stats.by_currency?.length">
          <p v-for="row in stats.by_currency" :key="`fee-${row.currency}`" class="kpi-value multi">
            {{ money(row.total_fee) }} <span class="ccy">{{ row.currency }}</span>
          </p>
        </template>
        <p v-else class="kpi-value">{{ money(0) }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getRemittanceStats } from '@/api/payments'
import { money } from '@/utils/format'

const loading = ref(false)
const period = ref('month')
const stats = reactive({
  remittance_count: 0,
  success_count: 0,
  success_rate: '0.00',
  by_currency: []
})

function formatRate(value) {
  if (value === null || value === undefined || value === '') return '0%'
  return `${value}%`
}

async function load() {
  loading.value = true
  try {
    const data = await getRemittanceStats({ period: period.value })
    stats.remittance_count = data.remittance_count ?? 0
    stats.success_count = data.success_count ?? 0
    stats.success_rate = data.success_rate ?? '0.00'
    stats.by_currency = data.by_currency || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.ptitle { margin: 0; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 6px 0 0; color: #909399; font-size: 13px; }
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.kpi-card { margin-bottom: 0; min-height: 120px; }
.kpi-label { margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #606266; }
.kpi-value { margin: 0; font-size: 26px; font-weight: 700; color: #303133; }
.kpi-value.multi { font-size: 20px; margin-bottom: 4px; }
.kpi-value .ccy { font-size: 13px; font-weight: 600; color: #909399; }
.kpi-hint { margin: 8px 0 0; font-size: 12px; color: #909399; }
</style>
