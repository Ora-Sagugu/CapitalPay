<template>
  <div>
    <PageHeader title="Transfers" subtitle="Remittance instructions awaiting Confirm transfer" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="filters.from_currency" placeholder="Source currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-select v-model="filters.to_currency" placeholder="Destination currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-input v-model="filters.search" placeholder="Order reference / PRN / customer / beneficiary" clearable style="width: 280px" @keyup.enter="reload" />
        <el-button type="primary" @click="reload">Search</el-button>
        <el-button @click="reset">Reset</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="order_no" label="Order reference" min-width="170" />
        <el-table-column prop="prn_code" label="PRN" min-width="110" />
        <el-table-column prop="merchant_name" label="Customer" min-width="130" />
        <el-table-column label="Currency pair" width="110">
          <template #default="{ row }">{{ row.from_currency }}/{{ row.to_currency || row.currency }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="Amount" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="fee_amount" label="Remittance Fee" min-width="120" :formatter="formatMoneyCell" />
        <el-table-column prop="beneficiary_name" label="Beneficiary" min-width="120" />
        <el-table-column label="Status" width="140">
          <template #default="{ row }"><StatusPill :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Creation Time" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canConfirmTransfer(row)" link type="warning" @click="doConfirmTransfer(row)">Confirm transfer</el-button>
          </template>
        </el-table-column>
        <template #empty><EmptyState message="No remittance instructions awaiting Confirm transfer" /></template>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>

    <el-dialog v-model="payoutVisible" title="Select payout bank" width="980px" destroy-on-close>
      <p class="payout-hint">
        Banks are ranked by Bank Fee (lowest first). Bank Fee is taken from Remittance Fee and must be lower.
        If the cheapest bank's remaining balance cannot cover the payout, select it plus a second bank for the remainder.
      </p>
      <p v-if="payoutMeta.amount" class="payout-meta">
        Payout {{ money(payoutMeta.amount) }} {{ payoutMeta.currency }}
        <template v-if="payoutMeta.remittanceFee !== '' && payoutMeta.remittanceFee != null">
          · Remittance Fee {{ money(payoutMeta.remittanceFee) }} {{ payoutMeta.currency }}
        </template>
      </p>
      <p v-if="payoutSplitSummary" class="payout-split">{{ payoutSplitSummary }}</p>
      <el-table :data="payoutBanks" v-loading="payoutLoading" size="small" class="payout-banks">
        <el-table-column label="" width="50">
          <template #default="{ row }">
            <el-checkbox
              :model-value="payoutBankCodes.includes(row.bank_code)"
              :disabled="isPayoutBankDisabled(row, payoutBanks, payoutBankCodes, payoutMeta.amount)"
              @change="(checked) => togglePayoutBank(row.bank_code, checked)"
            />
          </template>
        </el-table-column>
          <el-table-column prop="bank_name" label="Bank" min-width="160" />
          <el-table-column prop="bank_code" label="Code" width="90" />
          <el-table-column label="Fee Rule" width="100">
            <template #default="{ row }">{{ feeRuleText(row.fee_rate) }}</template>
          </el-table-column>
          <el-table-column label="Bank Fee" width="120">
            <template #default="{ row }">{{ money(row.computed_fee) }}</template>
          </el-table-column>
          <el-table-column label="Balance" width="130">
            <template #default="{ row }">{{ money(row.balance) }} {{ row.currency }}</template>
          </el-table-column>
          <el-table-column label="This payout" width="120">
            <template #default="{ row }">
              <template v-if="payoutLegAmount(row, payoutBanks, payoutBankCodes, payoutMeta.amount) !== ''">
                {{ money(payoutLegAmount(row, payoutBanks, payoutBankCodes, payoutMeta.amount)) }}
              </template>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="170">
            <template #default="{ row }">
              <el-tag v-if="row.recommended" type="success" size="small">Recommended</el-tag>
              <el-tag v-else-if="row.partial" type="warning" size="small">Remaining {{ money(row.usable_amount || row.balance) }}</el-tag>
              <el-tag v-else-if="!row.sufficient" type="info" size="small">Insufficient</el-tag>
              <el-tag v-else-if="!row.bank_fee_ok" type="warning" size="small">Fee too high</el-tag>
            </template>
          </el-table-column>
        </el-table>
      <el-empty v-if="!payoutLoading && !payoutBanks.length" description="No active payout banks" />
      <template #footer>
        <el-button @click="payoutVisible = false">Cancel</el-button>
        <el-button
          type="primary"
          :disabled="!payoutCanSubmit"
          :loading="payoutSubmitting"
          @click="submitPayout"
        >Confirm transfer</el-button>
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
import { confirmTransfer, getPayoutBanks, getPendingTransfers } from '@/api/orders'
import { unwrapList, datetime, money, CURRENCIES, formatMoneyCell } from '@/utils/format'
import { canConfirmTransferStatus } from '@/utils/remittanceTransfer'
import {
  confirmTransferPayload,
  isPayoutBankDisabled,
  payoutLegAmount,
  payoutSelectionComplete,
  recommendedPayoutCodes,
  splitPayoutLegs
} from '@/utils/payoutBanks'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canExecute = computed(() => auth.hasPermission('feature:fund_transfers'))

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const payoutVisible = ref(false)
const payoutLoading = ref(false)
const payoutSubmitting = ref(false)
const payoutBanks = ref([])
const payoutBankCodes = ref([])
const payoutOrderNo = ref('')
const payoutMeta = reactive({ amount: '', currency: '', remittanceFee: '' })
const filters = reactive({ search: '', from_currency: '', to_currency: '' })
const kpis = computed(() => [
  { label: 'Awaiting Confirm transfer', value: total.value }
])
const payoutCanSubmit = computed(() => payoutSelectionComplete(
  payoutBanks.value, payoutBankCodes.value, payoutMeta.amount,
))
const payoutSplitSummary = computed(() => {
  const legs = splitPayoutLegs(payoutBanks.value, payoutBankCodes.value, payoutMeta.amount)
  if (legs.length !== 2) return ''
  const ccy = payoutMeta.currency
  return legs
    .map((leg) => `${leg.bank_code} ${money(leg.payout_amount)} ${ccy}`)
    .join(' + ')
})

function canConfirmTransfer(row) {
  return canExecute.value && canConfirmTransferStatus(row)
}

function togglePayoutBank(code, checked) {
  if (checked) {
    if (!payoutBankCodes.value.includes(code)) {
      payoutBankCodes.value = [...payoutBankCodes.value, code]
    }
    return
  }
  payoutBankCodes.value = payoutBankCodes.value.filter((item) => item !== code)
}

function feeRuleText(rate) {
  if (rate === null || rate === undefined || rate === '') return '—'
  const n = Number(rate)
  if (Number.isNaN(n)) return '—'
  const pct = n * 100
  const formatted = pct.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4
  })
  return `${formatted}%`
}

async function load() {
  loading.value = true
  try {
    const data = await getPendingTransfers({
      page: page.value,
      page_size: pageSize,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally {
    loading.value = false
  }
}
function reload() { page.value = 1; load() }
function reset() { Object.assign(filters, { search: '', from_currency: '', to_currency: '' }); reload() }
function onPage(p) { page.value = p; load() }

async function doConfirmTransfer(row) {
  payoutOrderNo.value = row.order_no
  payoutBanks.value = []
  payoutBankCodes.value = []
  payoutMeta.amount = ''
  payoutMeta.currency = ''
  payoutMeta.remittanceFee = ''
  payoutVisible.value = true
  payoutLoading.value = true
  try {
    const data = await getPayoutBanks(row.order_no)
    payoutBanks.value = data.results || []
    payoutMeta.amount = data.amount || ''
    payoutMeta.currency = data.currency || ''
    payoutMeta.remittanceFee = data.remittance_fee ?? ''
    payoutBankCodes.value = recommendedPayoutCodes(data)
  } finally {
    payoutLoading.value = false
  }
}

async function submitPayout() {
  if (!payoutOrderNo.value || !payoutCanSubmit.value) return
  payoutSubmitting.value = true
  try {
    await confirmTransfer(payoutOrderNo.value, confirmTransferPayload(payoutBankCodes.value))
    ElMessage.success('The transfer has been confirmed.')
    payoutVisible.value = false
    load()
  } finally {
    payoutSubmitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.payout-hint {
  margin: 0 0 8px;
  color: #8c8c8c;
  font-size: 13px;
}
.payout-meta {
  margin: 0 0 12px;
  font-size: 13px;
}
.payout-banks {
  display: block;
  width: 100%;
}
.payout-split {
  margin: 0 0 12px;
  font-size: 13px;
  color: #3d3d3d;
}
</style>
