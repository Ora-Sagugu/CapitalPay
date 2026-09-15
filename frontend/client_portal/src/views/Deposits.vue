<template>
  <div>
    <PageHeader title="Deposits" subtitle="Customer deposit (credit) applications" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Reference / customer / narrative" clearable style="width: 220px" @keyup.enter="reload" />
        <el-select v-model="filters.currency" placeholder="Currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 130px" @change="reload">
          <el-option label="Pending review" value="PENDING" /><el-option label="Approved" value="APPROVED" /><el-option label="Rejected" value="REJECTED" />
        </el-select>
        <el-button type="primary" @click="openCreate">Create deposit transfer</el-button>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="deposit_no" label="Deposit reference" min-width="150" />
        <el-table-column label="Source" min-width="120">
          <template #default="{ row }">{{ row.source === 'AGENT_SELF' ? 'Agent' : 'Customer' }}</template>
        </el-table-column>
        <el-table-column prop="merchant_name" label="Customer name" min-width="140" />
        <el-table-column prop="agent_name" label="Agent" min-width="140" />
        <el-table-column prop="account_no" label="Linked account" min-width="140" />
        <el-table-column prop="currency" label="Currency" min-width="110" />
        <el-table-column prop="amount" label="Amount" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column label="Status" width="100"><template #default="{ row }"><StatusPill kind="deposit" :value="row.status" /></template></el-table-column>
        <el-table-column prop="reviewed_by" label="Reviewing officer" min-width="100" />
        <el-table-column label="Reviewed at" min-width="160"><template #default="{ row }">{{ datetime(row.reviewed_at) }}</template></el-table-column>
        <el-table-column prop="remark" label="Narrative" min-width="120" />
        <el-table-column label="Creation Time" min-width="160"><template #default="{ row }">{{ datetime(row.created_at) }}</template></el-table-column>
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING' && canApprove" link type="success" @click="review(row, 'approve')">Approve</el-button>
            <el-button v-if="row.status === 'PENDING' && canApprove" link type="danger" @click="review(row, 'reject')">Reject</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>
    <el-dialog v-model="visible" title="Create deposit transfer" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Customer">
          <el-select v-model="form.merchant" filterable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.merchant_name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Account">
          <el-select v-model="form.account" filterable style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="`${a.account_no} ${a.currency}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Currency">
          <el-select v-model="form.currency" style="width: 100%"><el-option v-for="c in CURRENCIES" :key="c.value" :label="c.label" :value="c.value" /></el-select>
        </el-form-item>
        <el-form-item label="Amount"><el-input v-model="form.amount" /></el-form-item>
        <el-form-item label="Narrative"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Submit</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getDeposits, getDepositStats, createDeposit, reviewDeposit, getNostroAccounts } from '@/api/accounts'
import { getMerchants } from '@/api/merchants'
import { unwrapList, datetime, CURRENCIES, formatMoneyCell } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:deposits.approve'))

const rows = ref([])
const stats = ref({})
const merchants = ref([])
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const visible = ref(false)
const filters = reactive({ search: '', currency: '', status: '' })
const form = reactive({ merchant: '', account: '', currency: 'USD', amount: '', remark: '' })
const kpis = computed(() => [
  { label: 'Total deposit instructions', value: stats.value.total_count ?? 0 },
  { label: 'Pending review', value: stats.value.pending ?? 0 },
  { label: 'Approved', value: stats.value.approved ?? 0 },
  { label: 'Credited today', value: stats.value.today_approved ?? 0 }
])
async function load() {
  loading.value = true
  try {
    stats.value = await getDepositStats()
    const data = await getDeposits({ page: page.value, page_size: pageSize, search: filters.search || undefined, currency: filters.currency || undefined, status: filters.status || undefined })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function openCreate() { visible.value = true }
async function save() {
  await createDeposit(form)
  ElMessage.success('The deposit-transfer application has been submitted.')
  visible.value = false
  load()
}
async function review(row, action) {
  let reason = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    reason = value
  }
  await reviewDeposit(row.deposit_no, { action, reason })
  ElMessage.success('The deposit-transfer application has been processed.')
  load()
}
onMounted(async () => {
  merchants.value = unwrapList(await getMerchants({ page_size: 100 })).rows
  accounts.value = unwrapList(await getNostroAccounts({ page_size: 100 })).rows
  load()
})
</script>
