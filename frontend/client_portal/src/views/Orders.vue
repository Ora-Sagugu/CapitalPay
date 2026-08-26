<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="订单号 / PRN / 商户 / 收款人" clearable style="width: 260px" @keyup.enter="reload" />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 160px" @change="reload">
        <el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
      <el-button type="success" @click="$router.push({ name: 'remittance-apply' })">新建汇款</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="order_no" label="订单号" min-width="180" />
      <el-table-column prop="prn_code" label="PRN" min-width="120" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="amount" label="金额" min-width="100" />
      <el-table-column label="币种" min-width="100">
        <template #default="{ row }">{{ row.from_currency }}/{{ row.to_currency || row.currency }}</template>
      </el-table-column>
      <el-table-column prop="beneficiary_name" label="收款人" min-width="120" />
      <el-table-column prop="fee_amount" label="手续费" min-width="90" />
      <el-table-column prop="status" label="状态" min-width="130" />
      <el-table-column label="操作" fixed="right" width="320">
        <template #default="{ row }">
          <el-button v-if="row.status === 'PENDING_REVIEW'" link type="success" @click="doReview(row, 'approve')">通过</el-button>
          <el-button v-if="row.status === 'PENDING_REVIEW'" link type="danger" @click="doReview(row, 'reject')">驳回</el-button>
          <el-button v-if="row.status === 'PENDING_PAY'" link type="primary" @click="doConfirmPay(row)">确认付款</el-button>
          <el-button v-if="['PENDING_PAY','PAY_RECEIVED'].includes(row.status)" link type="warning" @click="doConfirmTransfer(row)">确认转账</el-button>
          <el-button v-if="['PENDING_PAY','PAY_RECEIVED','PENDING_SETTLE','SETTLED'].includes(row.status)" link type="danger" @click="doRefund(row)">退款</el-button>
          <el-button v-if="row.contract_file" link @click="viewContract(row)">合同</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getOrders, reviewOrder, confirmPayment, confirmTransfer, initiateOrderRefund
} from '@/api/orders'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', status: '' })
const statusOptions = [
  'PENDING_REVIEW', 'PENDING_PAY', 'PAY_RECEIVED', 'PENDING_SETTLE',
  'SETTLED', 'COMPLETED', 'CLOSED', 'REFUNDING', 'REFUNDED'
]

async function load() {
  loading.value = true
  try {
    const data = await getOrders({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      status: filters.status || undefined
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
function reset() {
  filters.search = ''
  filters.status = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}

async function doReview(row, action) {
  let reason = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回汇款', { inputPattern: /.+/, inputErrorMessage: '必填' })
    reason = value
  } else {
    await ElMessageBox.confirm(`确认通过订单 ${row.order_no}？`, '审核通过')
  }
  await reviewOrder(row.order_no, { action, reason })
  ElMessage.success(action === 'approve' ? '已通过，进入待付款' : '已驳回并关闭')
  load()
}
async function doConfirmPay(row) {
  await ElMessageBox.confirm(`确认已收款 ${row.order_no}？`, '确认付款')
  await confirmPayment(row.order_no, {})
  ElMessage.success('已确认付款')
  load()
}
async function doConfirmTransfer(row) {
  await ElMessageBox.confirm(`确认银行转账已发起，进入待结算？`, '确认转账')
  await confirmTransfer(row.order_no, {})
  ElMessage.success('已进入待清算')
  load()
}
async function doRefund(row) {
  const { value: amount } = await ElMessageBox.prompt('退款金额', '发起退款', {
    inputValue: String(row.amount),
    inputPattern: /.+/,
  })
  const { value: reason } = await ElMessageBox.prompt('退款原因', '发起退款', { inputPattern: /.+/ })
  await initiateOrderRefund(row.order_no, { refund_amount: amount, reason })
  ElMessage.success('退款申请已提交')
  load()
}
function viewContract(row) {
  ElMessageBox.alert(row.contract_file, '合同文件')
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
