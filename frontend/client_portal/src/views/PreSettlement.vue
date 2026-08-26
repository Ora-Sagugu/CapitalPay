<template>
  <el-card class="page-card" shadow="never">
    <template #header>
      <div class="header">
        <span class="card-title">预清算管理</span>
        <el-tag type="warning">PENDING_SETTLE</el-tag>
      </div>
    </template>
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="订单号 / PRN / 商户" clearable style="width: 240px" @keyup.enter="reload" />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="loadStats">刷新统计</el-button>
    </div>
    <el-row :gutter="12" style="margin-bottom: 16px" v-if="stats">
      <el-col :span="6"><el-statistic title="待清算笔数" :value="stats.total_count" /></el-col>
      <el-col :span="6"><el-statistic title="金额合计" :value="stats.total_amount" /></el-col>
      <el-col :span="6"><el-statistic title="结算金额" :value="stats.total_settle_amount" /></el-col>
      <el-col :span="6"><el-statistic title="手续费" :value="stats.total_fee" /></el-col>
    </el-row>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="order_no" label="订单号" min-width="180" />
      <el-table-column prop="prn_code" label="PRN" min-width="120" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="amount" label="金额" min-width="100" />
      <el-table-column prop="settle_amount" label="结算金额" min-width="110" />
      <el-table-column prop="beneficiary_name" label="收款人" min-width="120" />
      <el-table-column prop="status" label="状态" width="140" />
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
    </el-table>
    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getPreorders, getPreorderStats } from '@/api/orders'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const stats = ref(null)
const filters = reactive({ search: '' })

async function load() {
  loading.value = true
  try {
    const data = await getPreorders({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
async function loadStats() {
  stats.value = await getPreorderStats()
}
function reload() {
  page.value = 1
  load()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(() => {
  load()
  loadStats()
})
</script>

<style scoped>
.header { display: flex; align-items: center; gap: 12px; }
.card-title { font-weight: 600; }
.toolbar { margin: 12px 0; display: flex; gap: 8px; }
</style>
