<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="入账号 / 商户" clearable style="width: 220px" @keyup.enter="reload" />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="reload">
        <el-option label="待审核" value="PENDING" />
        <el-option label="已通过" value="APPROVED" />
        <el-option label="已拒绝" value="REJECTED" />
      </el-select>
      <el-select v-model="filters.currency" placeholder="币种" clearable style="width: 120px" @change="reload">
        <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="deposit_no" label="入账号" min-width="160" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="amount" label="金额" min-width="110" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="created_at" label="申请时间" min-width="160" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'PENDING'">
            <el-button link type="success" @click="review(row, 'approve')">通过</el-button>
            <el-button link type="danger" @click="review(row, 'reject')">拒绝</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDeposits, reviewDeposit } from '@/api/accounts'

const currencies = ['USD', 'EUR', 'GBP', 'CNY', 'JPY', 'HKD']
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', status: '', currency: '' })

async function load() {
  loading.value = true
  try {
    const data = await getDeposits({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      status: filters.status || undefined,
      currency: filters.currency || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  load()
}
function onPage(p) {
  page.value = p
  load()
}
async function review(row, action) {
  let reason = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('拒绝原因', '拒绝入账', { inputPattern: /.+/ })
    reason = value
  } else {
    await ElMessageBox.confirm(`确认通过入账 ${row.deposit_no}？`, '审核')
  }
  await reviewDeposit(row.deposit_no, { action, reason })
  ElMessage.success(action === 'approve' ? '已入账' : '已拒绝')
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
