<template>
  <div>
    <PageHeader title="Overview" :subtitle="dateLabel" />
    <KpiCards :items="topCards" />
    <KpiCards :items="midCards" :span="8" />

    <div class="page-card">
      <div class="chart-head">
        <div class="section-title">Daily remittance volume</div>
        <div class="chart-tools">
          <el-radio-group v-model="chartType" size="small" @change="renderChart">
            <el-radio-button value="area">Area</el-radio-button>
            <el-radio-button value="bar">Bar</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="range" size="small" @change="load">
            <el-radio-button value="7d">7 days</el-radio-button>
            <el-radio-button value="1m">1 month</el-radio-button>
            <el-radio-button value="3m">3 months</el-radio-button>
            <el-radio-button value="6m">6 months</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div ref="chartRef" style="height: 320px" />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import { getDashboard } from '@/api/dashboard'
import { formatLongDate, money } from '@/utils/format'

const dateLabel = formatLongDate()
const stats = ref({})
const chartRef = ref(null)
const chartType = ref('area')
const range = ref('7d')
let chart = null

const topCards = computed(() => [
  { label: 'Remittances today', value: stats.value.today_remittance?.count ?? 0, hint: `Aggregate amount: $${money(stats.value.today_remittance?.amount)}`, icon: 'Sort', bg: '#eaf3ff', color: '#4a90e2' },
  { label: 'Outstanding', value: stats.value.pending?.count ?? 0, hint: 'Pending review / authorised', icon: 'Clock', bg: '#fff3e8', color: '#f08040' },
  { label: 'Completed', value: stats.value.completed?.count ?? 0, hint: 'Transferred / completed', icon: 'CircleCheck', bg: '#e9f8ef', color: '#67c23a' },
  { label: 'Failed', value: stats.value.failed?.count ?? 0, hint: 'Rejected / refunded / cancelled', icon: 'CircleClose', bg: '#fdecee', color: '#d0021b' }
])
const midCards = computed(() => [
  { label: 'Customers', value: stats.value.customers_total ?? 0, icon: 'User', bg: '#f3e8ff', color: '#9b59b6', span: 8 },
  { label: 'Agents', value: stats.value.agents_total ?? 0, icon: 'UserFilled', bg: '#e9f8ef', color: '#67c23a', span: 8 },
  { label: 'Remittance volume', value: stats.value.orders_total ?? 0, icon: 'Document', bg: '#eaf3ff', color: '#4a90e2', span: 8 }
])

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const trend = stats.value.trend || []
  const option = {
    tooltip: { trigger: 'axis', valueFormatter: (v) => money(v) },
    grid: { left: 48, right: 20, top: 24, bottom: 32 },
    xAxis: { type: 'category', data: trend.map((d) => d.date), boundaryGap: chartType.value === 'bar' },
    yAxis: { type: 'value' },
    series: [{
      type: chartType.value === 'bar' ? 'bar' : 'line',
      data: trend.map((d) => d.amount),
      smooth: true,
      areaStyle: chartType.value === 'area' ? { color: 'rgba(240,128,64,0.25)' } : undefined,
      itemStyle: { color: '#f08040' },
      lineStyle: { color: '#f08040', width: 2 },
      barWidth: 18
    }]
  }
  chart.setOption(option, true)
}

async function load() {
  stats.value = await getDashboard({ range: range.value })
  renderChart()
}

function resize() { chart && chart.resize() }

onMounted(() => {
  load()
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
</script>

<style scoped>
.chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.chart-tools { display: flex; gap: 10px; }
</style>
