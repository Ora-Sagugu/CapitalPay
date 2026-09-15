<template>
  <div>
    <PageHeader
      title="Bank Notifications"
      subtitle="Inbound credits matched by PRN. Mock ingest — bank API is not connected."
    />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input
          v-model="filters.search"
          placeholder="PRN / order / customer / bank"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
        />
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 160px" @change="reload">
          <el-option label="Matched" value="MATCHED" />
          <el-option label="Amount mismatch" value="MISMATCH" />
          <el-option label="Unmatched" value="UNMATCHED" />
          <el-option label="Received" value="RECEIVED" />
        </el-select>
        <el-select v-model="filters.currency" placeholder="Currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-button type="primary" @click="openSimulate">Simulate inbound credit</el-button>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="prn_code" label="PRN" width="110" />
        <el-table-column prop="order_no" label="Order" min-width="150" show-overflow-tooltip />
        <el-table-column prop="merchant_name" label="Customer" min-width="160" show-overflow-tooltip />
        <el-table-column label="Collection bank" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ bankLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="Amount" width="120" :formatter="formatMoneyCell" />
        <el-table-column prop="currency" label="Ccy" width="70" />
        <el-table-column label="Status" width="140">
          <template #default="{ row }"><StatusPill kind="bankNotification" :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Credit time" width="170">
          <template #default="{ row }">{{ datetime(row.txn_time) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">Details</el-button>
          </template>
        </el-table-column>
        <template #empty><EmptyState message="No bank credit notifications" /></template>
      </el-table>
      <el-pagination
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="560px">
      <div v-loading="detailLoading">
        <el-descriptions title="Credit" :column="1" border>
          <el-descriptions-item label="Notification">{{ dash(detail.notification_no) }}</el-descriptions-item>
          <el-descriptions-item label="Bank txn id">{{ dash(detail.txn_id) }}</el-descriptions-item>
          <el-descriptions-item label="Credit time">{{ datetime(detail.txn_time) }}</el-descriptions-item>
          <el-descriptions-item label="Amount">{{ money(detail.amount) }} {{ detail.currency || '' }}</el-descriptions-item>
          <el-descriptions-item label="Status"><StatusPill kind="bankNotification" :value="detail.status" /></el-descriptions-item>
          <el-descriptions-item label="Remark">{{ dash(detail.remark) }}</el-descriptions-item>
          <el-descriptions-item label="Source">{{ detail.source === 'MOCK' ? 'Mock ingest' : dash(detail.source) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Collection bank" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="Bank">{{ dash(detail.bank_name) }}</el-descriptions-item>
          <el-descriptions-item label="Bank code">{{ dash(detail.bank_code) }}</el-descriptions-item>
          <el-descriptions-item label="Account">{{ dash(detail.account_no) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Matched remittance" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="PRN">{{ dash(detail.prn_code) }}</el-descriptions-item>
          <el-descriptions-item label="Order">{{ dash(detail.order_no) }}</el-descriptions-item>
          <el-descriptions-item label="Customer">{{ customerLabel(detail) }}</el-descriptions-item>
          <el-descriptions-item label="Order status">{{ dash(orderStatusLabel(detail.order_status)) }}</el-descriptions-item>
          <el-descriptions-item label="Expected amount">
            {{ detail.expected_amount ? `${money(detail.expected_amount)} ${detail.expected_currency || ''}` : '—' }}
          </el-descriptions-item>
        </el-descriptions>
        <el-descriptions v-if="detail.collection_va" title="Collection VA" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="VA number">{{ dash(detail.collection_va.va_number) }}</el-descriptions-item>
          <el-descriptions-item label="Master account">{{ dash(detail.collection_va.master_account_no) }}</el-descriptions-item>
          <el-descriptions-item label="Master bank">{{ dash(detail.collection_va.master_bank_name) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-drawer>

    <el-dialog v-model="simulateVisible" title="Simulate inbound credit" width="520px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Awaiting funds">
          <el-select
            v-model="form.order_no"
            filterable
            clearable
            placeholder="Optional — pick a PRN order"
            style="width: 100%"
            @change="onOrderPicked"
          >
            <el-option
              v-for="order in awaitingOrders"
              :key="order.order_no"
              :label="`${order.prn_code || 'No PRN'} · ${order.order_no} · ${order.merchant_name || ''}`"
              :value="order.order_no"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="PRN"><el-input v-model="form.prn_code" placeholder="e.g. A25503" /></el-form-item>
        <el-form-item label="Amount"><el-input v-model="form.amount" /></el-form-item>
        <el-form-item label="Currency">
          <el-select v-model="form.currency" style="width: 100%">
            <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="Collection bank">
          <el-select v-model="form.nostro_id" filterable clearable placeholder="Platform collection account" style="width: 100%">
            <el-option
              v-for="account in collectionBanks"
              :key="account.id"
              :label="`${account.bank_name} · ${account.account_no} · ${account.currency}`"
              :value="account.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Remark"><el-input v-model="form.remark" placeholder="Optional bank memo" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="simulateVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="saveSimulate">Create notification</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import EmptyState from '@/components/EmptyState.vue'
import { getBankNotifications, getBankNotificationDetail, getBankNotificationStats, simulateBankCredit } from '@/api/bankNotifications'
import { getNostroAccounts } from '@/api/accounts'
import { getOrders } from '@/api/orders'
import { unwrapList, datetime, money, formatMoneyCell, CURRENCIES, ORDER_STATUS, statusLabel } from '@/utils/format'

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})
const simulateVisible = ref(false)
const saving = ref(false)
const awaitingOrders = ref([])
const accounts = ref([])
const filters = reactive({ search: '', status: '', currency: '' })
const form = reactive({
  order_no: '',
  prn_code: '',
  amount: '',
  currency: 'USD',
  nostro_id: '',
  remark: ''
})

const kpis = computed(() => [
  { label: 'Total credits', value: stats.value.total_count ?? 0 },
  { label: 'Matched', value: stats.value.matched ?? 0 },
  { label: 'Unmatched', value: stats.value.unmatched ?? 0 },
  { label: 'Credited today', value: stats.value.today_count ?? 0 }
])
const collectionBanks = computed(() => {
  const all = accounts.value || []
  const collection = all.filter((row) => row.account_type === 'COLLECTION')
  return collection.length ? collection : all
})
const detailTitle = computed(() => {
  if (detail.value.prn_code) return `PRN ${detail.value.prn_code}`
  return detail.value.notification_no || 'Bank notification'
})

function dash(value) {
  return value || '—'
}
function bankLabel(row) {
  const name = row.bank_name || row.bank_code || ''
  if (name && row.account_no) return `${name} · ${row.account_no}`
  return name || row.account_no || '—'
}
function customerLabel(row) {
  if (row.merchant_name && row.merchant_no) return `${row.merchant_name} (${row.merchant_no})`
  return row.merchant_name || row.merchant_no || '—'
}
function orderStatusLabel(code) {
  return statusLabel(ORDER_STATUS, code)
}

async function load() {
  loading.value = true
  try {
    stats.value = await getBankNotificationStats()
    const data = await getBankNotifications({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      status: filters.status || undefined,
      currency: filters.currency || undefined
    })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
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

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await getBankNotificationDetail(row.notification_no)
  } finally {
    detailLoading.value = false
  }
}

function resetForm() {
  form.order_no = ''
  form.prn_code = ''
  form.amount = ''
  form.currency = 'USD'
  form.nostro_id = collectionBanks.value[0]?.id || ''
  form.remark = ''
}

async function openSimulate() {
  resetForm()
  simulateVisible.value = true
  const [orderData, accountData] = await Promise.all([
    getOrders({ status: 'PENDING_PAY', page_size: 50 }),
    accounts.value.length ? Promise.resolve(null) : getNostroAccounts({ page_size: 100 })
  ])
  awaitingOrders.value = unwrapList(orderData).rows.filter((row) => row.prn_code)
  if (accountData) accounts.value = unwrapList(accountData).rows
  if (!form.nostro_id) form.nostro_id = collectionBanks.value[0]?.id || ''
}

function onOrderPicked(orderNo) {
  const order = awaitingOrders.value.find((row) => row.order_no === orderNo)
  if (!order) return
  form.prn_code = order.prn_code || ''
  form.amount = order.amount || ''
  form.currency = order.from_currency || order.currency || 'USD'
  if (order.prn_code) form.remark = `PRN:${order.prn_code}`
}

async function saveSimulate() {
  if (!form.prn_code && !form.order_no && !form.remark) {
    ElMessage.warning('Enter a PRN or pick an awaiting-funds order.')
    return
  }
  saving.value = true
  try {
    const payload = {
      prn_code: form.prn_code || undefined,
      order_no: form.order_no || undefined,
      amount: form.amount || undefined,
      currency: form.currency || undefined,
      nostro_id: form.nostro_id || undefined,
      remark: form.remark || undefined
    }
    await simulateBankCredit(payload)
    ElMessage.success('Mock bank credit recorded. The remittance was not auto-confirmed.')
    simulateVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  accounts.value = unwrapList(await getNostroAccounts({ page_size: 100 })).rows
  load()
})
</script>
