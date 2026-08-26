<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option label="待审批" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已拒绝" value="rejected" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="application_no" label="调账单号" min-width="180" />
      <el-table-column prop="bank_channel" label="银行通道" min-width="160" />
      <el-table-column prop="adjustment_amount" label="调账金额" min-width="120" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="reason" label="原因" min-width="200" />
      <el-table-column prop="status" label="状态" min-width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="approve(row)" :disabled="row.status !== 'pending'">通过</el-button>
          <el-button link type="danger" @click="reject(row)" :disabled="row.status !== 'pending'">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAdjustments, approveAdjustment, rejectAdjustment } from '@/api/adjustment'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ status: '' })

async function load() {
  loading.value = true
  try {
    const data = await getAdjustments({ page: page.value, page_size: pageSize.value, status: filters.status || undefined })
    rows.value = data.results || []
    total.value = data.count || data.total || 0
  } finally {
    loading.value = false
  }
}
async function approve(row) {
  await approveAdjustment(row.id, { action: 'approve', approver: 'admin', comment: '通过' })
  ElMessage.success('已通过')
  load()
}
async function reject(row) {
  await rejectAdjustment(row.id, { action: 'reject', approver: 'admin', comment: '拒绝' })
  ElMessage.success('已拒绝')
  load()
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.status = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
