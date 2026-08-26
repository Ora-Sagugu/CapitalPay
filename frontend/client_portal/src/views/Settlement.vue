<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="结算批次号" clearable style="width: 220px" @keyup.enter="reload" />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option label="待审批" value="PENDING" />
        <el-option label="已审批" value="APPROVED" />
        <el-option label="已结算" value="SETTLED" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="batch_no" label="批次号" min-width="180" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="settle_date" label="结算日期" min-width="140" />
      <el-table-column prop="settle_net_amount" label="结算金额" min-width="120" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="status" label="状态" min-width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="approve(row)" :disabled="row.status !== 'PENDING'">审批</el-button>
          <el-button link type="success" @click="exportBatch(row)">导出</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-tabs v-model="activeTab" class="toolbar" @tab-change="onTab">
      <el-tab-pane label="结算明细" name="details" />
      <el-tab-pane label="分润" name="shares" />
      <el-tab-pane label="差异核销" name="writeoffs" />
    </el-tabs>

    <el-table :data="subRows" v-loading="subLoading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="ref_key" label="关联单号" min-width="180" />
      <el-table-column prop="amount" label="金额" min-width="120" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="status" label="状态" min-width="120" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettleBatches, approveSettleBatch, exportSettleBatch, getSettleDetails, getFeeShares, getDifferenceWriteoffs } from '@/api/settlement'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', status: '' })

const activeTab = ref('details')
const subRows = ref([])
const subLoading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getSettleBatches({ page: page.value, page_size: pageSize.value, search: filters.search || undefined, status: filters.status || undefined })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
async function loadSub() {
  subLoading.value = true
  try {
    const fn = { details: getSettleDetails, shares: getFeeShares, writeoffs: getDifferenceWriteoffs }[activeTab.value]
    const data = await fn({ page: 1, page_size: 20 })
    subRows.value = data.results || []
  } finally {
    subLoading.value = false
  }
}
async function approve(row) {
  await approveSettleBatch(row.id)
  ElMessage.success('审批通过')
  load()
}
function exportBatch(row) {
  exportSettleBatch(row.id).then(() => ElMessage.success('已触发导出')).catch(() => {})
}
function onTab() {
  loadSub()
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.search = ''
  filters.status = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(() => {
  load()
  loadSub()
})
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
