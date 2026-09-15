<template>
  <div>
    <PageHeader title="Refunds" subtitle="Initiate refunds against completed remittances and credit the proceeds to the customer account" />
    <KpiCards :items="kpis" />
    <el-alert type="warning" :closable="false" class="fee-banner">
      Refund charge rate {{ feeRate }}%
      <el-button link type="primary" @click="setFee">Configure</el-button>
    </el-alert>
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Refund reference / remittance reference / customer" clearable style="width: 240px" @keyup.enter="reload" />
        <el-select v-model="filters.status" placeholder="All statuses" clearable style="width: 140px" @change="reload">
          <el-option label="Pending review" value="PENDING_REVIEW" />
          <el-option label="In process" value="PROCESSING" />
          <el-option label="Successful" value="SUCCESS" />
          <el-option label="Rejected" value="REJECTED" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="refund_no" label="Refund no." min-width="160" />
        <el-table-column prop="order_no" label="Order No." min-width="160" />
        <el-table-column prop="merchant_name" label="Customer" min-width="130" />
        <el-table-column prop="refund_amount" label="Amount" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="refund_fee_amount" label="Charges" min-width="90" :formatter="formatMoneyCell" />
        <el-table-column prop="refund_reason" label="Reason" min-width="140" />
        <el-table-column label="Status" width="110">
          <template #default="{ row }"><StatusPill :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Creation Time" min-width="160"><template #default="{ row }">{{ datetime(row.created_at) }}</template></el-table-column>
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING_REVIEW' && canApprove" link type="success" @click="review(row, 'approve')">Approve</el-button>
            <el-button v-if="row.status === 'PENDING_REVIEW' && canApprove" link type="danger" @click="review(row, 'reject')">Reject</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusPill from '@/components/StatusPill.vue'
import KpiCards from '@/components/KpiCards.vue'
import { getRefunds, getRefundStats, getRefundFeeConfig, reviewRefund } from '@/api/refunds'
import request from '@/api/request'
import { unwrapList, datetime, money, formatMoneyCell } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:refunds.approve'))

const rows = ref([])
const stats = ref({})
const feeRate = ref('0.1')
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ search: '', status: '' })
const kpis = computed(() => [
  { label: 'Total refund instructions', value: stats.value.total_count ?? 0 },
  { label: 'Pending review', value: stats.value.pending_review ?? 0 },
  { label: 'Refunds today', value: stats.value.today_count ?? 0 },
  { label: 'Aggregate refund amount', value: money(stats.value.total_amount) }
])
async function load() {
  loading.value = true
  try {
    stats.value = await getRefundStats()
    const cfg = await getRefundFeeConfig()
    feeRate.value = cfg.fee_rate
    const data = await getRefunds({ page: page.value, page_size: pageSize, search: filters.search || undefined, status: filters.status || undefined })
    const u = unwrapList(data)
    rows.value = u.rows.map((r) => ({ ...r, order_no: r.order_no || r.payment_order_no }))
    total.value = u.total
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
async function review(row, action) {
  let comment = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    comment = value
  }
  await reviewRefund(row.refund_no, { action, comment })
  ElMessage.success('The refund application has been processed.')
  load()
}
async function setFee() {
  const { value } = await ElMessageBox.prompt('Refund charge rate (%)', 'Configure', { inputValue: String(feeRate.value) })
  await request.put('/v1/admin/refunds/fee-config/', { fee_rate: value })
  ElMessage.success('The refund charge rate has been updated.')
  load()
}
onMounted(load)
</script>

<style scoped>
.fee-banner { margin-bottom: 14px; }
</style>
