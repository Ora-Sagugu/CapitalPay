<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in cards" :key="item.label">
        <el-card class="page-card" shadow="hover">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="page-card" style="margin-top: 16px" shadow="never">
      <template #header><span class="card-title">订单概况</span></template>
      <div ref="chartRef" style="height: 280px"></div>
    </el-card>

    <el-card class="page-card" style="margin-top: 16px" shadow="never">
      <template #header><span class="card-title">最新汇款</span></template>
      <el-table :data="latest" v-loading="loadingLatest" border stripe>
        <el-table-column prop="order_no" label="订单号" min-width="180" />
        <el-table-column prop="merchant_name" label="商户" min-width="140" />
        <el-table-column prop="amount" label="金额" width="110" />
        <el-table-column prop="status" label="状态" width="130" />
        <el-table-column prop="beneficiary_name" label="收款人" min-width="120" />
        <el-table-column prop="created_at" label="时间" min-width="160" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import * as echarts from 'echarts'
import { getOrderStats } from '@/api/dashboard'
import { getOrders } from '@/api/orders'

const stats = ref({ pending_review: 0, pending_pay: 0, completed_count: 0, today_amount: 0 })
const chartRef = ref(null)
const latest = ref([])
const loadingLatest = ref(false)
let chart = null

const cards = computed(() => [
  { label: '待审核订单', value: stats.value.pending_review },
  { label: '待支付订单', value: stats.value.pending_pay },
  { label: '已完成笔数', value: stats.value.completed_count },
  { label: '今日金额', value: stats.value.today_amount }
])

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: ['待审核', '待支付', '已完成'] },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: [stats.value.pending_review, stats.value.pending_pay, stats.value.completed_count],
      itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
      barWidth: 40
    }]
  })
}

async function load() {
  try {
    stats.value = await getOrderStats()
    renderChart()
  } catch (e) { /* interceptor */ }
  loadingLatest.value = true
  try {
    const data = await getOrders({ page: 1, page_size: 8, ordering: '-created_at' })
    latest.value = data.results || []
  } finally {
    loadingLatest.value = false
  }
}

function resize() {
  chart && chart.resize()
}

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
.stat-label { color: #8c8c8c; font-size: 14px; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 8px; color: #1890ff; }
.card-title { font-weight: 600; }
</style>
