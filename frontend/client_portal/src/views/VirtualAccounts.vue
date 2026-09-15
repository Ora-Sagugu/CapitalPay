<template>
  <div>
    <PageHeader title="Virtual Accounts" subtitle="Customer collection VAs linked to a pooled nostro" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Customer / VA number" clearable style="width: 220px" @keyup.enter="reload" />
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 140px" @change="reload">
          <el-option label="Active" value="ACTIVE" /><el-option label="Inactive" value="INACTIVE" /><el-option label="Revoked" value="REVOKED" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="merchant_name" label="Customer" min-width="160" />
        <el-table-column prop="merchant_no" label="Customer number" min-width="150" />
        <el-table-column prop="va_count" label="VA count" min-width="100" />
        <el-table-column label="Currencies" min-width="180">
          <template #default="{ row }">{{ (row.currencies || []).join(', ') }}</template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="110" />
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">Details</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>
    <el-drawer v-model="detailVisible" :title="detailTitle" size="70%">
      <el-table :data="detailAccounts">
        <el-table-column prop="va_number" label="VA number" min-width="170" />
        <el-table-column prop="currency" label="Currency" min-width="100" />
        <el-table-column prop="balance" label="Balance" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="status" label="Status" width="110" />
        <el-table-column prop="master_account_no" label="Master account" min-width="150" />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link @click="openTx(row)">Ledger</el-button>
            <el-button link type="danger" @click="revoke(row)">Revoke</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <el-dialog v-model="txVisible" title="VA ledger" width="720px">
      <el-table :data="txns">
        <el-table-column prop="type" label="Type" />
        <el-table-column prop="amount" label="Amount" :formatter="formatMoneyCell" />
        <el-table-column prop="status_label" label="Status" />
        <el-table-column prop="created_at" label="Date/time" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import { getVirtualAccountsByCustomer, getVirtualAccountStats, getVaTransactions, revokeVa } from '@/api/accounts'
import { unwrapList, formatMoneyCell } from '@/utils/format'

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ search: '', status: '' })
const detailVisible = ref(false)
const detail = ref(null)
const txVisible = ref(false)
const txns = ref([])
const kpis = computed(() => [
  { label: 'All', value: stats.value.total ?? 0 },
  { label: 'Active', value: stats.value.active ?? 0 },
  { label: 'Inactive', value: stats.value.inactive ?? 0 },
  { label: 'Revoked', value: stats.value.revoked ?? 0 }
])
const detailTitle = computed(() => {
  if (!detail.value) return 'Virtual Accounts'
  return `${detail.value.merchant_name || detail.value.merchant_no} virtual accounts`
})
const detailAccounts = computed(() => detail.value?.accounts || [])

async function load() {
  loading.value = true
  try {
    stats.value = await getVirtualAccountStats()
    const data = await getVirtualAccountsByCustomer({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      status: filters.status || undefined
    })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
    if (detail.value) {
      const next = rows.value.find((row) => row.merchant === detail.value.merchant)
      if (next) detail.value = next
    }
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}
async function openTx(row) {
  const data = await getVaTransactions(row.id)
  txns.value = data.transactions || []
  txVisible.value = true
}
async function revoke(row) {
  const { value } = await ElMessageBox.prompt('Revocation reason', 'Revoke virtual account', { inputPattern: /.+/, inputErrorMessage: 'A reason is required.' })
  await revokeVa(row.id, { reason: value })
  load()
}
onMounted(load)
</script>
