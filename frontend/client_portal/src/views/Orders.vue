<template>
  <div>
    <PageHeader title="Orders" subtitle="Review and monitor remittance instructions" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-select v-model="filters.from_currency" placeholder="Source currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-select v-model="filters.to_currency" placeholder="Destination currency" clearable style="width: 120px" @change="reload">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-input v-model="filters.search" placeholder="Order reference / PRN / customer / beneficiary" clearable style="width: 260px" @keyup.enter="reload" />
        <el-button type="primary" @click="reload">Search</el-button>
        <el-button @click="reset">Reset</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="order_no" label="Order reference" min-width="170" />
        <el-table-column prop="prn_code" label="PRN" min-width="110" />
        <el-table-column prop="merchant_name" label="Customer" min-width="130" />
        <el-table-column label="Currency pair" width="110"><template #default="{ row }">{{ row.from_currency }}/{{ row.to_currency || row.currency }}</template></el-table-column>
        <el-table-column prop="amount" label="Amount" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="fee_amount" label="Charges" min-width="90" :formatter="formatMoneyCell" />
        <el-table-column label="Charge Bearer" min-width="280">
          <template #default="{ row }">{{ FEE_BEARING[row.fee_bearing] || row.fee_bearing || '—' }}</template>
        </el-table-column>
        <el-table-column prop="beneficiary_name" label="Beneficiary" min-width="120" />
        <el-table-column prop="reviewed_by" label="Reviewing officer" min-width="140" />
        <el-table-column label="Creation Time" min-width="160"><template #default="{ row }">{{ datetime(row.created_at) }}</template></el-table-column>
        <el-table-column label="Actions" width="540" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">View</el-button>
            <el-button link type="primary" @click="openScreening(row)">Screening</el-button>
            <el-button v-if="row.status === 'PENDING_REVIEW' && canApprove" link type="success" @click="doReview(row, 'approve')">Approve</el-button>
            <el-button v-if="row.status === 'PENDING_REVIEW' && canApprove" link type="danger" @click="doReview(row, 'reject')">Reject</el-button>
            <el-button v-if="canApprove && row.status === 'PENDING_PAY'" link type="success" @click="doConfirmPayment(row)">Confirm payment</el-button>
            <el-button v-if="canConfirmTransfer(row)" link type="warning" @click="doConfirmTransfer(row)">Confirm transfer</el-button>
            <span v-else-if="isAwaitingAgentPayout(row)" class="awaiting-payout">Awaiting agent payout request</span>
            <el-button v-if="canApprove && ['PENDING_PAY','PAY_RECEIVED','PENDING_SETTLE','SETTLED'].includes(row.status)" link type="danger" @click="doRefund(row)">Refund</el-button>
            <el-button v-if="row.contract_file" link @click="viewContract(row)">Contract</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>

    <el-drawer
      v-model="detailVisible"
      :title="detailTitle"
      size="760px"
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <template v-if="detail">
          <h3 class="section-title">Instruction Overview</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Order Reference" :span="2">{{ dash(detail.order_no) }}</el-descriptions-item>
            <el-descriptions-item label="Customer Order No.">{{ dash(detail.merchant_order_no) }}</el-descriptions-item>
            <el-descriptions-item label="Status">
              <StatusPill :value="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="Unique ID (UIN)">{{ dash(detail.unique_identification_no) }}</el-descriptions-item>
            <el-descriptions-item label="PRN">{{ dash(detail.prn_code) }}</el-descriptions-item>
            <el-descriptions-item label="Customer">{{ dash(detail.merchant_name) }}</el-descriptions-item>
            <el-descriptions-item label="Customer No.">{{ dash(detail.merchant_no) }}</el-descriptions-item>
            <el-descriptions-item label="End-User ID">{{ dash(detail.user_id) }}</el-descriptions-item>
            <el-descriptions-item label="Idempotency Key" :span="2">{{ dash(detail.idempotency_key) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Amount &amp; FX</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Currency Pair">
              {{ dash(detail.from_currency) }} / {{ dash(detail.to_currency || detail.currency) }}
            </el-descriptions-item>
            <el-descriptions-item label="Principal Amount">
              {{ money(detail.amount) }} {{ detail.from_currency || detail.currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item label="Charges">
              {{ money(detail.fee_amount) }} {{ detail.fee_currency || detail.from_currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item label="Charge Bearer">
              {{ FEE_BEARING[detail.fee_bearing] || detail.fee_bearing || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="Sender Total Due">
              {{ money(detail.sender_total_amount) }} {{ detail.from_currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item label="Beneficiary Receives">
              {{ money(detail.settle_amount) }} {{ detail.to_currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item label="Exchange Rate">{{ dash(detail.exchange_rate) }}</el-descriptions-item>
            <el-descriptions-item label="Rate Source">{{ dash(detail.rate_source) }}</el-descriptions-item>
            <el-descriptions-item label="Fee Model">{{ dash(detail.applied_fee_model) }}</el-descriptions-item>
            <el-descriptions-item label="Fee Rate">{{ dash(detail.applied_fee_rate) }}</el-descriptions-item>
            <el-descriptions-item label="Fixed Fee">{{ money(detail.applied_fixed_fee) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Beneficiary</h3>
          <el-descriptions :column="1" border size="small" class="detail-block">
            <el-descriptions-item label="Name">{{ dash(detail.beneficiary_name) }}</el-descriptions-item>
            <el-descriptions-item label="Bank">{{ dash(detail.beneficiary_bank) }}</el-descriptions-item>
            <el-descriptions-item label="Account">{{ dash(detail.beneficiary_account) }}</el-descriptions-item>
            <el-descriptions-item label="SWIFT / BIC">{{ dash(detail.beneficiary_swift) }}</el-descriptions-item>
            <el-descriptions-item label="Address">{{ dash(detail.beneficiary_address) }}</el-descriptions-item>
            <el-descriptions-item label="Purpose">{{ dash(detail.remittance_purpose) }}</el-descriptions-item>
            <el-descriptions-item label="Supporting Contract">
              <el-button v-if="detail.contract_file" link type="primary" @click="viewContract(detail)">Open Contract</el-button>
              <span v-else>—</span>
            </el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Payment &amp; Banking</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Payment Method">
              {{ detail.pay_method_display || PAY_METHOD[detail.pay_method] || detail.pay_method || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="Bank Code">{{ dash(detail.bank_code) }}</el-descriptions-item>
            <el-descriptions-item label="Bank Transaction ID" :span="2">{{ dash(detail.bank_txn_id) }}</el-descriptions-item>
          </el-descriptions>

          <template v-if="detail.agent_review_status && detail.agent_review_status !== 'none'">
          <h3 class="section-title">Agent Review</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Agent Review Status">{{ dash(detail.agent_review_status) }}</el-descriptions-item>
            <el-descriptions-item label="Agent Reviewer">{{ dash(detail.agent_reviewed_by) }}</el-descriptions-item>
            <el-descriptions-item label="Agent Reviewed At">{{ datetime(detail.agent_reviewed_at) }}</el-descriptions-item>
            <el-descriptions-item label="Agent Comment" :span="2">{{ dash(detail.agent_review_comment) }}</el-descriptions-item>
          </el-descriptions>
          </template>

          <template v-if="detail.agent_payout_request_status && detail.agent_payout_request_status !== 'none'">
          <h3 class="section-title">Agent Payout Request</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Status">{{ payoutRequestLabel(detail) }}</el-descriptions-item>
            <el-descriptions-item label="Requested By">{{ dash(detail.agent_payout_requested_by) }}</el-descriptions-item>
            <el-descriptions-item label="Requested At" :span="2">{{ datetime(detail.agent_payout_requested_at) }}</el-descriptions-item>
          </el-descriptions>
          </template>

          <h3 class="section-title">Operations Review</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Reviewing Officer">{{ dash(detail.reviewed_by) }}</el-descriptions-item>
            <el-descriptions-item label="Reviewed At">{{ datetime(detail.reviewed_at) }}</el-descriptions-item>
            <el-descriptions-item label="Review Comment" :span="2">{{ dash(detail.review_comment) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Key Timestamps</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Created">{{ datetime(detail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="Expires">{{ datetime(detail.expire_at) }}</el-descriptions-item>
            <el-descriptions-item label="Collection Confirmed">{{ datetime(detail.pay_received_at) }}</el-descriptions-item>
            <el-descriptions-item label="Settled">{{ datetime(detail.settled_at) }}</el-descriptions-item>
            <el-descriptions-item label="Completed">{{ datetime(detail.completed_at) }}</el-descriptions-item>
            <el-descriptions-item label="Closed">{{ datetime(detail.closed_at) }}</el-descriptions-item>
            <el-descriptions-item label="Last Updated">{{ datetime(detail.updated_at) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Webhook Notification</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Notify URL" :span="2">{{ dash(detail.notify_url) }}</el-descriptions-item>
            <el-descriptions-item label="Notify Status">{{ dash(detail.notify_status) }}</el-descriptions-item>
            <el-descriptions-item label="Notify Attempts">{{ detail.notify_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="Last Notify At" :span="2">{{ datetime(detail.last_notify_at) }}</el-descriptions-item>
          </el-descriptions>

          <template v-if="detail.quote_detail">
            <h3 class="section-title">Linked Quote</h3>
            <el-descriptions :column="2" border size="small" class="detail-block">
              <el-descriptions-item label="Quote No.">{{ dash(detail.quote_detail.quote_no) }}</el-descriptions-item>
              <el-descriptions-item label="Quote Status">{{ dash(detail.quote_detail.status) }}</el-descriptions-item>
              <el-descriptions-item label="Quoted Amount">
                {{ money(detail.quote_detail.amount) }} {{ detail.quote_detail.from_currency }}
              </el-descriptions-item>
              <el-descriptions-item label="Quoted Settle">
                {{ money(detail.quote_detail.settle_amount) }} {{ detail.quote_detail.to_currency }}
              </el-descriptions-item>
              <el-descriptions-item label="Quote Rate">{{ dash(detail.quote_detail.exchange_rate) }}</el-descriptions-item>
              <el-descriptions-item label="Quote Source">{{ dash(detail.quote_detail.rate_source) }}</el-descriptions-item>
              <el-descriptions-item label="Sender Fee">{{ money(detail.quote_detail.sender_fee_amount) }}</el-descriptions-item>
              <el-descriptions-item label="Beneficiary Fee">{{ money(detail.quote_detail.beneficiary_fee_amount) }}</el-descriptions-item>
              <el-descriptions-item label="Quote Expires">{{ datetime(detail.quote_detail.expires_at) }}</el-descriptions-item>
              <el-descriptions-item label="Quote Used">{{ datetime(detail.quote_detail.used_at) }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <h3 class="section-title">Progress</h3>
          <el-timeline class="detail-block">
            <el-timeline-item
              v-for="step in detail.timeline || []"
              :key="step.code"
              :timestamp="datetime(step.at)"
              :type="step.verified ? 'success' : (step.active ? 'primary' : 'info')"
              :hollow="!step.verified && !step.active"
            >
              {{ step.title }}
            </el-timeline-item>
          </el-timeline>

          <template v-if="detail.refunds?.length">
            <h3 class="section-title">Refunds</h3>
            <el-table :data="detail.refunds" size="small" class="detail-block">
              <el-table-column prop="refund_no" label="Refund No." min-width="150" />
              <el-table-column prop="refund_amount" label="Amount" min-width="100" :formatter="formatMoneyCell" />
              <el-table-column prop="status" label="Status" min-width="120" />
              <el-table-column prop="refund_reason" label="Reason" min-width="180" show-overflow-tooltip />
              <el-table-column label="Created" min-width="150">
                <template #default="{ row }">{{ datetime(row.created_at) }}</template>
              </el-table-column>
            </el-table>
          </template>

          <el-collapse v-if="detail.status_history?.length" class="history-collapse">
            <el-collapse-item title="Status History (Raw)" name="history">
              <el-timeline>
                <el-timeline-item
                  v-for="(item, idx) in detail.status_history"
                  :key="idx"
                  :timestamp="datetime(item.at || item.time)"
                >
                  {{ formatHistoryEntry(item) }}
                </el-timeline-item>
              </el-timeline>
            </el-collapse-item>
          </el-collapse>
        </template>
      </div>
    </el-drawer>

    <el-drawer
      v-model="screeningVisible"
      :title="screeningTitle"
      size="760px"
      destroy-on-close
    >
      <div v-loading="screeningLoading">
        <template v-if="screening">
          <h3 class="section-title">Screening Summary</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Result">
              <el-tag :type="screening.is_clear ? 'success' : 'danger'" size="small">
                {{ screening.is_clear ? 'Clear' : 'Hits' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Blocking Condition Met">
              {{ screening.blocked ? 'Yes' : 'No' }}
            </el-descriptions-item>
            <el-descriptions-item label="Total Hits">{{ screening.total_hits ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="Warning Message" :span="2">{{ dash(screening.warning_message) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Screened Fields</h3>
          <el-descriptions :column="2" border size="small" class="detail-block">
            <el-descriptions-item label="Beneficiary Name" :span="2">{{ dash(screening.screened?.beneficiary_name) }}</el-descriptions-item>
            <el-descriptions-item label="Beneficiary Address" :span="2">{{ dash(screening.screened?.beneficiary_address) }}</el-descriptions-item>
            <el-descriptions-item label="Customer">{{ dash(screening.screened?.customer_name) }}</el-descriptions-item>
            <el-descriptions-item label="Customer Sanction Status">{{ dash(screening.screened?.customer_sanction_status) }}</el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">Name Hits</h3>
          <el-table :data="screening.name_hits || []" size="small" class="detail-block">
            <el-table-column prop="entity_name" label="Matched Entity" min-width="170" />
            <el-table-column prop="list_type" label="List Source" width="110" />
            <el-table-column label="Risk Level" min-width="110">
              <template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template>
            </el-table-column>
            <el-table-column label="Match Type" min-width="130">
              <template #default="{ row }">{{ formatMatchType(row.match_type) }}</template>
            </el-table-column>
            <el-table-column label="Match Score" min-width="110">
              <template #default="{ row }">{{ formatScore(row.score) }}</template>
            </el-table-column>
            <el-table-column prop="country" label="Country" min-width="120" />
            <el-table-column prop="reason" label="Reason" min-width="180" show-overflow-tooltip />
            <template #empty><EmptyState message="No Name Hits" /></template>
          </el-table>

          <h3 class="section-title">Address Hits</h3>
          <el-table :data="screening.address_hits || []" size="small" class="detail-block">
            <el-table-column prop="entity_name" label="Matched Entity" min-width="170" />
            <el-table-column prop="list_type" label="List Source" width="110" />
            <el-table-column label="Risk Level" min-width="110">
              <template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template>
            </el-table-column>
            <el-table-column label="Match Type" min-width="150">
              <template #default="{ row }">{{ formatMatchType(row.match_type) }}</template>
            </el-table-column>
            <el-table-column prop="keyword" label="Keyword" min-width="160" show-overflow-tooltip />
            <el-table-column prop="country" label="Country" min-width="120" />
            <template #empty><EmptyState message="No Address Hits" /></template>
          </el-table>

          <h3 class="section-title">Country Hits</h3>
          <el-table :data="screening.country_hits || []" size="small" class="detail-block">
            <el-table-column prop="country" label="Country" min-width="140" />
            <el-table-column prop="keyword" label="Keyword" min-width="140" />
            <el-table-column prop="list_type" label="List Source" width="110" />
            <el-table-column label="Risk Level" min-width="110">
              <template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template>
            </el-table-column>
            <el-table-column label="Match Type" min-width="140">
              <template #default="{ row }">{{ formatMatchType(row.match_type) }}</template>
            </el-table-column>
            <el-table-column label="Field" min-width="150">
              <template #default="{ row }">{{ formatMatchType(row.field) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="Reason" min-width="180" show-overflow-tooltip />
            <template #empty><EmptyState message="No Country Hits" /></template>
          </el-table>
        </template>
      </div>
    </el-drawer>

    <el-dialog v-model="payoutVisible" title="Select payout bank" width="780px" destroy-on-close>
      <p class="payout-hint">
        Banks are ranked by Fee Rule (lowest first). The first bank with sufficient balance is recommended.
      </p>
      <p v-if="payoutMeta.amount" class="payout-meta">
        Payout {{ money(payoutMeta.amount) }} {{ payoutMeta.currency }}
      </p>
      <el-radio-group v-model="payoutBankCode" class="payout-banks">
        <el-table :data="payoutBanks" v-loading="payoutLoading" size="small">
          <el-table-column label="" width="50">
            <template #default="{ row }">
              <el-radio :value="row.bank_code" :disabled="!row.sufficient" />
            </template>
          </el-table-column>
        <el-table-column prop="bank_name" label="Bank" min-width="160" />
        <el-table-column prop="bank_code" label="Code" width="90" />
        <el-table-column label="Fee Rule" width="100">
          <template #default="{ row }">{{ feeRuleText(row.fee_rate) }}</template>
        </el-table-column>
        <el-table-column label="Computed fee" width="120">
          <template #default="{ row }">{{ money(row.computed_fee) }}</template>
        </el-table-column>
        <el-table-column label="Balance" width="130">
          <template #default="{ row }">{{ money(row.balance) }} {{ row.currency }}</template>
        </el-table-column>
        <el-table-column label="" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.recommended" type="success" size="small">Recommended</el-tag>
            <el-tag v-else-if="!row.sufficient" type="info" size="small">Insufficient</el-tag>
          </template>
        </el-table-column>
      </el-table>
      </el-radio-group>
      <el-empty v-if="!payoutLoading && !payoutBanks.length" description="No active payout banks" />
      <template #footer>
        <el-button @click="payoutVisible = false">Cancel</el-button>
        <el-button
          type="primary"
          :disabled="!payoutBankCode"
          :loading="payoutSubmitting"
          @click="submitPayout"
        >Confirm transfer</el-button>
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
import EmptyState from '@/components/EmptyState.vue'
import { getOrders, getOrderDetail, getOrderSanctionReview, reviewOrder, confirmPayment, confirmTransfer, getPayoutBanks, initiateOrderRefund } from '@/api/orders'
import { getOrderStats } from '@/api/dashboard'
import { unwrapList, datetime, money, PAY_METHOD, CURRENCIES, formatMoneyCell, FEE_BEARING } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:orders.approve'))

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const screeningVisible = ref(false)
const screeningLoading = ref(false)
const screening = ref(null)
const payoutVisible = ref(false)
const payoutLoading = ref(false)
const payoutSubmitting = ref(false)
const payoutBanks = ref([])
const payoutBankCode = ref('')
const payoutOrderNo = ref('')
const payoutMeta = reactive({ amount: '', currency: '' })
const filters = reactive({ search: '', from_currency: '', to_currency: '' })
const detailTitle = computed(() => detail.value?.order_no ? `Order ${detail.value.order_no}` : 'Order Details')
const screeningTitle = computed(() => screening.value?.order_no ? `Screening ${screening.value.order_no}` : 'Screening')
const kpis = computed(() => [
  { label: 'Awaiting operations review', value: stats.value.pending_review ?? 0 },
  { label: 'Awaiting funds', value: stats.value.pending_pay ?? 0 },
  { label: 'Remittance instructions today', value: stats.value.today_count ?? 0 }
])

function dash(value) {
  if (value === null || value === undefined || value === '') return '—'
  return value
}

function isAwaitingAgentPayout(row) {
  return row?.status === 'PAY_RECEIVED' && row?.agent_payout_request_status === 'pending'
}

function canConfirmTransfer(row) {
  if (!canApprove.value) return false
  const gate = row?.agent_payout_request_status || 'none'
  if (gate === 'pending') return false
  if (gate === 'requested') return row.status === 'PAY_RECEIVED'
  return ['PENDING_PAY', 'PAY_RECEIVED'].includes(row.status)
}

function payoutRequestLabel(row) {
  const status = row?.agent_payout_request_status
  if (status === 'pending') return 'Awaiting agent payout request'
  if (status === 'requested') return 'Agent requested payout'
  return dash(status)
}

const MATCH_TYPES = {
  exact_name: 'Exact Name',
  alias_name: 'Alias Name',
  fuzzy_name: 'Fuzzy Name',
  address_contains: 'Address Contains',
  country_match: 'Country Match',
  address_keyword: 'Address Keyword',
  country_name: 'Country Name'
}

function formatMatchType(value) {
  if (!value) return '—'
  return MATCH_TYPES[value] || value.replace(/_/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase())
}

function formatScore(value) {
  const score = Number(value)
  return Number.isFinite(score) ? `${(score * 100).toFixed(1)}%` : '—'
}

function formatHistoryEntry(item) {
  if (!item) return '—'
  const status = item.status || item.to || ''
  const from = item.from ? `${item.from} → ` : ''
  const extra = []
  if (item.reason) extra.push(`reason: ${item.reason}`)
  if (item.comment) extra.push(`comment: ${item.comment}`)
  if (item.operator) extra.push(`by: ${item.operator}`)
  const suffix = extra.length ? ` (${extra.join('; ')})` : ''
  return `${from}${status}${suffix}`
}

async function load() {
  loading.value = true
  try {
    stats.value = await getOrderStats()
    const data = await getOrders({ page: page.value, page_size: pageSize, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function reset() { Object.assign(filters, { search: '', from_currency: '', to_currency: '' }); reload() }
function onPage(p) { page.value = p; load() }

async function openDetail(row) {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getOrderDetail(row.order_no)
  } finally {
    detailLoading.value = false
  }
}

async function openScreening(row) {
  screeningVisible.value = true
  screening.value = null
  screeningLoading.value = true
  try {
    screening.value = await getOrderSanctionReview(row.order_no)
  } finally {
    screeningLoading.value = false
  }
}

async function doReview(row, action) {
  let comment = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    comment = value
  }
  await reviewOrder(row.order_no, { action, comment })
  ElMessage.success('The remittance instruction has been processed.')
  load()
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

async function doConfirmPayment(row) {
  await ElMessageBox.confirm(
    'Confirm that funds have arrived at the operations bank? The customer account will be credited the principal.',
    'Confirm payment',
    { type: 'warning' },
  )
  await confirmPayment(row.order_no)
  ElMessage.success('Funds received. The customer account has been credited.')
  load()
}

async function doConfirmTransfer(row) {
  payoutOrderNo.value = row.order_no
  payoutBanks.value = []
  payoutBankCode.value = ''
  payoutMeta.amount = ''
  payoutMeta.currency = ''
  payoutVisible.value = true
  payoutLoading.value = true
  try {
    const data = await getPayoutBanks(row.order_no)
    payoutBanks.value = data.results || []
    payoutMeta.amount = data.amount || ''
    payoutMeta.currency = data.currency || ''
    payoutBankCode.value = data.recommended_bank_code || ''
  } finally {
    payoutLoading.value = false
  }
}

async function submitPayout() {
  if (!payoutOrderNo.value || !payoutBankCode.value) return
  payoutSubmitting.value = true
  try {
    await confirmTransfer(payoutOrderNo.value, { bank_code: payoutBankCode.value })
    ElMessage.success('The transfer has been confirmed.')
    payoutVisible.value = false
    load()
  } finally {
    payoutSubmitting.value = false
  }
}
async function doRefund(row) {
  const { value } = await ElMessageBox.prompt('Enter the grounds for the refund', 'Initiate refund', { inputPattern: /.+/, inputErrorMessage: 'A refund reason is required.' })
  await initiateOrderRefund(row.order_no, { reason: value })
  ElMessage.success('The refund has been initiated.')
  load()
}
function viewContract(row) {
  const p = row.contract_file
  if (!p) return
  const url = /^https?:\/\//.test(p) || p.startsWith('/') ? p : `/media/${p}`
  window.open(url, '_blank')
}
onMounted(load)
</script>

<style scoped>
.section-title {
  margin: 20px 0 12px;
  font-size: 15px;
  font-weight: 600;
}
.section-title:first-child {
  margin-top: 0;
}
.detail-block {
  margin-bottom: 8px;
}
.history-collapse {
  margin-top: 16px;
}
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
.awaiting-payout {
  display: inline-block;
  margin: 0 8px;
  color: #8c8c8c;
  font-size: 12px;
}
</style>
