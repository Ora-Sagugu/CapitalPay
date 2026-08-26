<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="退款号 / 订单号 / PRN / 商户" clearable style="width: 260px" @keyup.enter="reload" />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option label="待审核" value="PENDING_REVIEW" />
        <el-option label="已通过" value="APPROVED" />
        <el-option label="已拒绝" value="REJECTED" />
        <el-option label="处理中" value="PROCESSING" />
        <el-option label="已完成" value="SUCCESS" />
        <el-option label="失败" value="FAILED" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="refund_no" label="退款单号" min-width="180" />
      <el-table-column prop="order_no" label="原订单号" min-width="180" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="amount" label="退款金额" min-width="120" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="status" label="状态" min-width="120" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="review(row)" :disabled="row.status !== 'PENDING_REVIEW'">审核</el-button>
          <el-button link type="success" @click="initiate(row)" :disabled="!['APPROVED', 'FAILED'].includes(row.status)">发起退款</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getRefunds, reviewRefund, initiateRefund } from '@/api/refunds'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', status: '' })

async function load() {
  loading.value = true
  try {
    const data = await getRefunds({ page: page.value, page_size: pageSize.value, search: filters.search || undefined, status: filters.status || undefined })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
async function review(row) {
  await reviewRefund(row.refund_no, { action: 'approve', reviewer: 'admin', remark: '后台审核通过' })
  ElMessage.success('审核通过')
  load()
}
async function initiate(row) {
  await initiateRefund(row.refund_no)
  ElMessage.success('已发起退款')
  load()
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
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
