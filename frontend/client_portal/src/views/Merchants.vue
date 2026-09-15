<template>
  <div>
    <PageHeader title="Profiles" subtitle="Customer directory, risk limits and KYC review" />
    <el-tabs v-model="pageTab" class="profiles-tabs" @tab-change="onPageTabChange">
      <el-tab-pane label="List" name="list">
        <KpiCards :items="kpis" />
        <div class="page-card">
          <div class="toolbar">
            <el-input v-model="filters.search" placeholder="Customer / number / legal person" clearable style="width: 240px" @keyup.enter="reload" />
            <el-select v-model="filters.risk_level" placeholder="Risk rating" clearable style="width: 140px" @change="reload">
              <el-option label="Low" value="LOW" /><el-option label="Medium" value="MEDIUM" /><el-option label="High" value="HIGH" />
            </el-select>
            <el-select v-model="filters.status" placeholder="Customer status" clearable style="width: 140px" @change="reload">
              <el-option label="Pending review" value="PENDING" /><el-option label="Active" value="ACTIVE" /><el-option label="Suspended" value="SUSPENDED" /><el-option label="Closed" value="CLOSED" />
            </el-select>
            <el-button @click="reload">Refresh</el-button>
          </div>
          <el-table :data="rows" v-loading="loading">
            <el-table-column prop="merchant_name" label="Customer name" min-width="140" />
            <el-table-column prop="merchant_no" label="Customer number" min-width="150" />
            <el-table-column label="Customer status" min-width="130"><template #default="{ row }"><StatusPill kind="merchant" :value="row.status" /></template></el-table-column>
            <el-table-column label="Risk rating" min-width="110"><template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template></el-table-column>
            <el-table-column v-if="ENABLE_AGENTS" prop="agent_name" label="Agent" min-width="120" />
            <el-table-column prop="max_single_amount" label="Single limit" min-width="100" :formatter="formatMoneyCell" />
            <el-table-column prop="daily_count" label="Daily count" min-width="110" />
            <el-table-column prop="daily_limit" label="Daily limit" min-width="100" :formatter="formatMoneyCell" />
            <el-table-column label="Account balance" min-width="110">
              <template #default="{ row }">{{ money(row.balance) }} {{ row.balance_currency }}</template>
            </el-table-column>
            <el-table-column prop="next_review_date" label="Next review" min-width="110" />
            <el-table-column prop="license_expiry_date" label="Licence expiry" min-width="110" />
            <el-table-column label="Actions" width="180" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row)">Details</el-button>
                <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
                <el-button link @click="showApiKey(row)">API Key</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="KYC" name="kyc" lazy>
        <KycReview embedded />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="editVisible" title="Customer Risk and Limits" width="520px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="Risk Rating">
          <el-select v-model="editForm.risk_level" style="width: 100%" @change="onRiskLevelChange">
            <el-option label="Low" value="LOW" /><el-option label="Medium" value="MEDIUM" /><el-option label="High" value="HIGH" /><el-option label="Blocked" value="BLOCKED" />
          </el-select>
        </el-form-item>
        <el-form-item label="Single Limit"><el-input v-model="editForm.max_single_amount" /></el-form-item>
        <el-form-item label="Daily Count"><el-input v-model="editForm.daily_count" /></el-form-item>
        <el-form-item label="Daily Limit"><el-input v-model="editForm.daily_limit" /></el-form-item>
        <el-form-item label="Licence Expiry"><el-date-picker v-model="editForm.license_expiry_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveEdit">Save</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="detailNo + ' customer settings'" size="70%">
      <el-tabs v-model="detailTab">
        <el-tab-pane label="KYC" name="kyc">
          <el-form :model="kycForm" label-width="140px">
            <el-form-item label="Legal person"><el-input v-model="kycForm.legal_person" /></el-form-item>
            <el-form-item label="ID number"><el-input v-model="kycForm.id_number" /></el-form-item>
            <el-form-item label="Licence number"><el-input v-model="kycForm.business_license" /></el-form-item>
            <el-form-item label="Business scope"><el-input v-model="kycForm.business_scope" /></el-form-item>
            <el-button type="primary" @click="saveKyc">Save KYC</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="Payment products" name="products">
          <el-button type="primary" size="small" @click="saveProduct">Save product</el-button>
          <el-form :model="productForm" label-width="120px" style="margin-top:12px">
            <el-form-item label="Product type">
              <el-select v-model="productForm.product_type" style="width: 100%">
                <el-option label="Online banking" value="ONLINE_BANK" /><el-option label="Authorised payment" value="AUTHORIZED" /><el-option label="Wire transfer" value="WIRE_TRANSFER" />
              </el-select>
            </el-form-item>
            <el-form-item label="Enabled"><el-switch v-model="productForm.is_enabled" /></el-form-item>
            <el-form-item label="Single limit"><el-input v-model="productForm.max_single_amount" /></el-form-item>
          </el-form>
          <el-table :data="products">
            <el-table-column prop="product_type" label="Product" /><el-table-column prop="is_enabled" label="Enabled" /><el-table-column prop="max_single_amount" label="Limit" :formatter="formatMoneyCell" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="Charges" name="fees">
          <el-alert
            type="info"
            show-icon
            :closable="false"
            title="Remittance charges are configured under Remittance → Remittance Fee and apply to every customer."
          />
        </el-tab-pane>
        <el-tab-pane label="Settlement accounts" name="settle">
          <el-form :model="acctForm" label-width="120px">
            <el-form-item label="Bank"><el-input v-model="acctForm.bank_name" /></el-form-item>
            <el-form-item label="Account name"><el-input v-model="acctForm.account_name" /></el-form-item>
            <el-form-item label="Account number"><el-input v-model="acctForm.account_number" /></el-form-item>
            <el-form-item label="Default"><el-switch v-model="acctForm.is_default" /></el-form-item>
            <el-button type="primary" @click="saveAcct">Create account</el-button>
          </el-form>
          <el-table :data="accounts" style="margin-top:12px">
            <el-table-column prop="bank_name" label="Bank" /><el-table-column prop="account_name" label="Account name" /><el-table-column prop="is_default" label="Default" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="Fee share" name="split">
          <el-form :model="splitForm" label-width="140px">
            <el-form-item label="Auto allocation"><el-switch v-model="splitForm.auto_split" /></el-form-item>
            <el-form-item label="Cycle (T+N)"><el-input v-model="splitForm.settlement_cycle" /></el-form-item>
            <el-form-item label="Customer ratio"><el-input v-model="splitForm.merchant_ratio" /></el-form-item>
            <el-form-item label="Platform ratio"><el-input v-model="splitForm.platform_ratio" /></el-form-item>
            <el-form-item v-if="ENABLE_AGENTS" label="Agent ratio"><el-input v-model="splitForm.agent_ratio" /></el-form-item>
            <el-button type="primary" @click="saveSplit">Save allocation</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="Settlement" name="funds">
          <el-button @click="loadFunds">Refresh</el-button>
          <el-button type="success" @click="doExportFunds">Export settled funds</el-button>
          <el-button type="success" @click="doExportOrders">Export settled orders</el-button>
          <h4>Funds pending settlement</h4>
          <el-table :data="pendingFunds"><el-table-column prop="order_no" label="Order" /><el-table-column prop="settle_amount" label="Settlement amount" :formatter="formatMoneyCell" /></el-table>
          <h4>Settled funds</h4>
          <el-table :data="settledFunds"><el-table-column prop="order_no" label="Order" /><el-table-column prop="settle_amount" label="Settlement amount" :formatter="formatMoneyCell" /></el-table>
          <h4>Orders pending settlement</h4>
          <el-table :data="pendingOrders"><el-table-column prop="order_no" label="Order" /><el-table-column prop="amount" label="Amount" :formatter="formatMoneyCell" /><el-table-column prop="status" label="Status" /></el-table>
          <h4>Settled orders</h4>
          <el-table :data="settledOrders"><el-table-column prop="order_no" label="Order" /><el-table-column prop="amount" label="Amount" :formatter="formatMoneyCell" /><el-table-column prop="status" label="Status" /></el-table>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import KycReview from '@/views/KycReview.vue'
import { getMerchants, getMerchant, getMerchantStats, updateMerchant, getMerchantKyc, setMerchantKyc, getSettlementAccounts, setSettlementAccount, getPaymentProducts, setPaymentProduct, getSplitConfig, saveSplitConfig, getPendingFunds, getSettledFunds, getPendingOrders, getSettledOrders, exportSettledFunds, exportSettledOrders } from '@/api/merchants'
import { getRiskRatingLimits } from '@/api/param'
import { unwrapList, money, formatMoneyCell } from '@/utils/format'
import { ENABLE_AGENTS } from '@/config/features'

const route = useRoute()
const router = useRouter()
const pageTab = ref(route.query.tab === 'kyc' ? 'kyc' : 'list')

function onPageTabChange(name) {
  const next = name === 'kyc' ? { tab: 'kyc' } : {}
  router.replace({ path: '/merchants', query: next })
}

watch(
  () => route.query.tab,
  (tab) => {
    pageTab.value = tab === 'kyc' ? 'kyc' : 'list'
  },
)

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ search: '', risk_level: '', status: '' })
const editVisible = ref(false)
const currentNo = ref('')
const editForm = reactive({ risk_level: 'MEDIUM', max_single_amount: '', daily_count: '', daily_limit: '', license_expiry_date: '' })
const riskLimitsByLevel = ref({})
const detailVisible = ref(false)
const detailNo = ref('')
const detailTab = ref('kyc')
const kycForm = reactive({ legal_person: '', id_number: '', business_license: '', business_scope: '' })
const productForm = reactive({ product_type: 'WIRE_TRANSFER', is_enabled: true, max_single_amount: '' })
const products = ref([])
const acctForm = reactive({ bank_name: '', account_name: '', account_number: '', is_default: true })
const accounts = ref([])
const splitForm = reactive({ auto_split: true, settlement_cycle: 1, merchant_ratio: '1', platform_ratio: '0', agent_ratio: '0' })
const pendingFunds = ref([])
const settledFunds = ref([])
const pendingOrders = ref([])
const settledOrders = ref([])

const kpis = computed(() => [
  { label: 'All customers', value: stats.value.total ?? 0, icon: 'User' },
  { label: 'Low risk', value: stats.value.low_risk ?? 0, icon: 'CircleCheck', bg: '#e9f8ef', color: '#67c23a' },
  { label: 'Medium risk', value: stats.value.medium_risk ?? 0, icon: 'Warning', bg: '#fff3e8', color: '#f08040' },
  { label: 'High risk', value: stats.value.high_risk ?? 0, icon: 'CircleClose', bg: '#fdecee', color: '#d0021b' },
  { label: 'Expiring within 30 days', value: stats.value.expiring_30 ?? 0, icon: 'Timer', span: 6 }
])

async function load() {
  loading.value = true
  try {
    stats.value = await getMerchantStats()
    const data = await getMerchants({ page: page.value, page_size: pageSize, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function applyRiskLimits(level) {
  const cfg = riskLimitsByLevel.value[level]
  if (!cfg) return
  editForm.max_single_amount = cfg.max_single_amount
  editForm.daily_count = cfg.daily_count
  editForm.daily_limit = riskDailyLimit(cfg)
}
function riskDailyLimit(cfg) {
  const single = Number(cfg?.max_single_amount)
  const count = Number(cfg?.daily_count)
  if (!Number.isFinite(single) || !Number.isFinite(count)) return cfg?.daily_limit ?? ''
  return (single * count).toFixed(2)
}
function onRiskLevelChange(level) {
  applyRiskLimits(level)
}
function openEdit(row) {
  currentNo.value = row.merchant_no
  Object.assign(editForm, {
    risk_level: row.risk_level,
    max_single_amount: row.max_single_amount, daily_count: row.daily_count,
    daily_limit: row.daily_limit, license_expiry_date: row.license_expiry_date
  })
  editVisible.value = true
}
async function saveEdit() {
  await updateMerchant(currentNo.value, editForm)
  ElMessage.success('The record has been saved.')
  editVisible.value = false
  load()
}
async function showApiKey(row) {
  const detail = await getMerchant(row.merchant_no)
  await ElMessageBox.alert(`API key: ${detail.api_key || '(the key is not returned in clear text)'}\nIntegration documentation: http://127.0.0.1:1024/api/docs/`, 'Customer platform integration', { confirmButtonText: 'Close' })
}
async function openDetail(row) {
  detailNo.value = row.merchant_no
  detailTab.value = 'kyc'
  detailVisible.value = true
  const kyc = await getMerchantKyc(row.merchant_no)
  Object.assign(kycForm, { legal_person: kyc.legal_person || '', id_number: kyc.id_number || '', business_license: kyc.business_license || '', business_scope: kyc.business_scope || '' })
  products.value = await getPaymentProducts(row.merchant_no)
  accounts.value = await getSettlementAccounts(row.merchant_no)
  Object.assign(splitForm, await getSplitConfig(row.merchant_no))
  await loadFunds()
}
async function saveKyc() {
  await setMerchantKyc(detailNo.value, kycForm)
  ElMessage.success('KYC has been saved.')
}
async function saveProduct() {
  await setPaymentProduct(detailNo.value, productForm)
  products.value = await getPaymentProducts(detailNo.value)
  ElMessage.success('The product has been saved.')
}
async function saveAcct() {
  await setSettlementAccount(detailNo.value, acctForm)
  accounts.value = await getSettlementAccounts(detailNo.value)
  ElMessage.success('The settlement account has been saved.')
}
async function saveSplit() {
  await saveSplitConfig(detailNo.value, splitForm)
  ElMessage.success('The fee-share allocation has been saved.')
}
async function loadFunds() {
  pendingFunds.value = await getPendingFunds(detailNo.value)
  settledFunds.value = await getSettledFunds(detailNo.value)
  pendingOrders.value = await getPendingOrders(detailNo.value)
  settledOrders.value = await getSettledOrders(detailNo.value)
}
function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}
async function doExportFunds() {
  downloadBlob(await exportSettledFunds(detailNo.value), `settled_funds_${detailNo.value}.xlsx`)
}
async function doExportOrders() {
  downloadBlob(await exportSettledOrders(detailNo.value), `settled_orders_${detailNo.value}.xlsx`)
}
onMounted(async () => {
  try {
    const data = await getRiskRatingLimits()
    const map = {}
    for (const row of unwrapList(data).rows) {
      map[row.risk_level] = row
    }
    riskLimitsByLevel.value = map
  } catch {
    riskLimitsByLevel.value = {}
  }
  load()
})
</script>

<style scoped>
.profiles-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
</style>
