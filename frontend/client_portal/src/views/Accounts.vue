<template>
  <div>
    <PageHeader title="Master Account" subtitle="USD / EUR / GBP / CNY / JPY / HKD" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="filters.merchant_id" placeholder="Customer" clearable filterable style="width: 180px" @change="reload">
          <el-option v-for="m in merchants" :key="m.id" :label="m.merchant_name" :value="m.id" />
        </el-select>
        <el-select v-model="filters.currency" placeholder="Currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-input v-model="filters.search" placeholder="Search by account number or bank" clearable style="width: 200px" @keyup.enter="reload" />
        <el-button @click="reload">Refresh</el-button>
        <el-button type="primary" @click="openCreate">Create account</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="account_no" label="Account number" min-width="150" />
        <el-table-column prop="bank_code" label="Bank Code" min-width="110" />
        <el-table-column prop="bank_name" label="Bank name" min-width="140" />
        <el-table-column prop="currency" label="Currency" min-width="110" />
        <el-table-column prop="balance" label="Balance" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="virtual_accounts_total" label="VA total" min-width="120" :formatter="formatMoneyCell" />
        <el-table-column prop="max_single_amount" label="Single limit" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="daily_limit" label="Daily limit" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="merchant_name" label="Linked customer" min-width="120" />
        <el-table-column prop="account_type" label="Account type" min-width="120" />
        <el-table-column label="Status" width="90">
          <template #default="{ row }"><StatusPill :value="row.is_active" /></template>
        </el-table-column>
        <el-table-column label="Book vs cash" min-width="120">
          <template #default><el-tag size="small" type="success">In agreement</el-tag></template>
        </el-table-column>
        <el-table-column label="Actions" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRecharge(row)">Top up</el-button>
            <el-button link @click="openTx(row)">Ledger</el-button>
            <el-button link type="warning" @click="deactivate(row)">Close</el-button>
            <el-button link type="danger" @click="remove(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createVisible" title="Create account" width="480px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="Customer">
          <el-select v-model="createForm.merchant" filterable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.merchant_name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Bank Code"><el-input v-model="createForm.bank_code" /></el-form-item>
        <el-form-item label="Bank name"><el-input v-model="createForm.bank_name" /></el-form-item>
        <el-form-item label="Currency">
          <el-select v-model="createForm.currency" style="width: 100%">
            <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveCreate">Save</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="txVisible" title="Transaction ledger" width="720px">
      <el-table :data="txns">
        <el-table-column prop="type" label="Type" />
        <el-table-column prop="amount" label="Amount" :formatter="formatMoneyCell" />
        <el-table-column prop="status_label" label="Status" />
        <el-table-column prop="ref_no" label="Reference" />
        <el-table-column prop="created_at" label="Date/time" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getNostroAccounts, getNostroStats, createNostroAccount, rechargeNostro, deactivateNostro, deleteNostroAccount, getNostroTransactions } from '@/api/accounts'
import { getMerchants } from '@/api/merchants'
import { unwrapList, CURRENCIES, money, formatMoneyCell } from '@/utils/format'

const rows = ref([])
const stats = ref({})
const merchants = ref([])
const loading = ref(false)
const filters = reactive({ merchant_id: '', currency: '', search: '' })
const createVisible = ref(false)
const createForm = reactive({ merchant: '', bank_code: '', bank_name: '', currency: 'USD' })
const txVisible = ref(false)
const txns = ref([])

const kpis = computed(() => [
  { label: 'Master Account', value: stats.value.total ?? 0, icon: 'Wallet' },
  { label: 'Active', value: stats.value.active ?? 0, icon: 'CircleCheck', bg: '#e9f8ef', color: '#67c23a' },
  { label: 'Currencies', value: stats.value.currency_count ?? 0, icon: 'Coin' },
  { label: 'Aggregate CNY balance', value: money(stats.value.cny_total), icon: 'Money' }
])

async function load() {
  loading.value = true
  try {
    stats.value = await getNostroStats()
    const params = { page_size: 50 }
    if (filters.merchant_id) params.merchant_id = filters.merchant_id
    if (filters.currency) params.currency = filters.currency
    if (filters.search) params.search = filters.search
    const data = await getNostroAccounts(params)
    rows.value = unwrapList(data).rows.filter((r) => !filters.search || `${r.account_no}${r.bank_code}${r.bank_name}`.includes(filters.search))
  } finally { loading.value = false }
}
function reload() { load() }
function openCreate() { createVisible.value = true }
async function saveCreate() {
  await createNostroAccount(createForm)
  ElMessage.success('The account has been created.')
  createVisible.value = false
  load()
}
async function openRecharge(row) {
  const { value } = await ElMessageBox.prompt('Top-up amount', 'Top up', { inputPattern: /.+/, inputErrorMessage: 'An amount is required.' })
  await rechargeNostro(row.id, { amount: value })
  ElMessage.success('The top-up has been posted.')
  load()
}
async function openTx(row) {
  const data = await getNostroTransactions(row.id)
  txns.value = data.transactions || []
  txVisible.value = true
}
async function deactivate(row) {
  const { value } = await ElMessageBox.prompt('Closure reason', 'Close account', { inputPattern: /.+/, inputErrorMessage: 'A reason is required.' })
  await deactivateNostro(row.id, { reason: value })
  load()
}
async function remove(row) {
  await ElMessageBox.confirm('Delete this record?', 'Confirmation', { type: 'warning' })
  await deleteNostroAccount(row.id)
  load()
}
onMounted(async () => {
  merchants.value = unwrapList(await getMerchants({ page_size: 100 })).rows
  load()
})
</script>
