<template>
  <div>
    <PageHeader v-if="!embedded" :title="pageTitle" :subtitle="pageSubtitle" />
    <KpiCards :items="kpis" :span="8" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Username / email / legal person" clearable style="width: 260px" @keyup.enter="reload" />
        <el-select v-model="filters.stage" placeholder="Stage" style="width: 180px" @change="reload">
          <el-option label="Needs review" value="needs_review" />
          <el-option label="Approved" value="approved" />
          <el-option label="Rejected" value="rejected" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="username" label="Username" min-width="170" />
        <el-table-column prop="email" label="Email" min-width="240" />
        <el-table-column label="Legal person" min-width="160">
          <template #default="{ row }">{{ row.legal_person || '—' }}</template>
        </el-table-column>
        <el-table-column label="ID type" min-width="130">
          <template #default="{ row }">{{ row.id_type || '—' }}</template>
        </el-table-column>
        <el-table-column label="Review status" min-width="150">
          <template #default="{ row }"><StatusPill kind="onboarding" :value="row.onboarding_status || row.status" /></template>
        </el-table-column>
        <el-table-column label="Submission Time" width="140">
          <template #default="{ row }">{{ formatDate(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" min-width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">View</el-button>
            <template v-if="isAgentQueue && canReview(row)">
              <el-button link type="success" :loading="submitting" @click="agreeFromList(row)">Agree</el-button>
              <el-button link type="danger" :loading="submitting" @click="rejectFromList(row)">Reject</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty><EmptyState /></template>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="640px">
      <div v-loading="detailLoading">
        <el-descriptions title="Profile" :column="1" border>
          <el-descriptions-item label="Username">{{ dash(detailUser?.username) }}</el-descriptions-item>
          <el-descriptions-item label="Legal Name">{{ dash(basic.legal_name) }}</el-descriptions-item>
          <el-descriptions-item label="ID Type">{{ dash(basic.id_type) }}</el-descriptions-item>
          <el-descriptions-item label="ID Number">{{ dash(basic.id_number) }}</el-descriptions-item>
          <el-descriptions-item label="Phone">{{ dash(basic.contact_phone) }}</el-descriptions-item>
          <el-descriptions-item label="Nationality">{{ dash(basic.nationality) }}</el-descriptions-item>
          <el-descriptions-item label="Address">{{ dash(basic.address) }}</el-descriptions-item>
          <el-descriptions-item label="Licence Expiry">{{ dash(basic.license_expiry_date) }}</el-descriptions-item>
        </el-descriptions>
        <template v-if="hasKyb">
          <el-descriptions title="Application" :column="1" border style="margin-top: 16px">
            <el-descriptions-item label="Application ref">{{ dash(kyb.application_ref || applicationRef) }}</el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="Market" :column="1" border style="margin-top: 16px">
            <el-descriptions-item label="Region">{{ dash(kyb.market?.name || kyb.region) }}</el-descriptions-item>
            <el-descriptions-item label="Registry">{{ dash(kyb.market?.registry) }}</el-descriptions-item>
            <el-descriptions-item label="Tax label">{{ dash(kyb.market?.tax_label) }}</el-descriptions-item>
            <el-descriptions-item label="Currency">{{ dash(kyb.currency) }}</el-descriptions-item>
            <el-descriptions-item label="Account type">{{ dash(kyb.account_type) }}</el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="Business" :column="1" border style="margin-top: 16px">
            <el-descriptions-item label="Legal name">{{ dash(kyb.business?.legal_name) }}</el-descriptions-item>
            <el-descriptions-item label="Trading name">{{ dash(kyb.business?.trading_name) }}</el-descriptions-item>
            <el-descriptions-item label="Industry">{{ dash(kyb.business?.industry) }}</el-descriptions-item>
            <el-descriptions-item label="Tax ID">{{ dash(kyb.business?.tax_id) }}</el-descriptions-item>
            <el-descriptions-item label="Email">{{ dash(kyb.business?.email) }}</el-descriptions-item>
            <el-descriptions-item label="Phone">{{ dash(kyb.business?.phone) }}</el-descriptions-item>
            <el-descriptions-item label="Address">{{ dash(kyb.business?.address) }}</el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="People" :column="1" border style="margin-top: 16px">
            <el-descriptions-item v-for="(person, i) in kybPeople" :key="i" :label="person.role || `Person ${i + 1}`">
              {{ person.name }}
              <span v-if="person.ownership_pct"> · {{ person.ownership_pct }}%</span>
              <span v-if="person.pep"> · PEP</span>
            </el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="Payout" :column="1" border style="margin-top: 16px">
            <el-descriptions-item label="Method">{{ dash(kyb.payout?.method) }}</el-descriptions-item>
            <el-descriptions-item label="Account name">{{ dash(kyb.payout?.account_name || finance.account_name) }}</el-descriptions-item>
            <el-descriptions-item label="Bank">{{ dash(kyb.payout?.bank || finance.bank_name) }}</el-descriptions-item>
            <el-descriptions-item label="Account number">{{ dash(kyb.payout?.account_number || finance.bank_account) }}</el-descriptions-item>
            <el-descriptions-item label="SWIFT">{{ dash(finance.swift_code) }}</el-descriptions-item>
            <el-descriptions-item label="Rule">{{ dash(kyb.payout?.rule) }}</el-descriptions-item>
            <el-descriptions-item label="Frequency">{{ dash(kyb.payout?.frequency) }}</el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="Settlement" :column="1" border style="margin-top: 16px">
            <el-descriptions-item label="Model">{{ dash(kyb.settlement_contract?.model) }}</el-descriptions-item>
            <el-descriptions-item label="Mandate mode">{{ dash(kyb.settlement_contract?.mandate_mode) }}</el-descriptions-item>
            <el-descriptions-item label="Cadence">{{ dash(kyb.settlement_contract?.cadence) }}</el-descriptions-item>
            <el-descriptions-item label="Customer settlement">{{ dash(kyb.settlement_contract?.customer_settlement_service) }}</el-descriptions-item>
            <el-descriptions-item label="Mandate ref">{{ dash(kyb.settlement_mandate?.reference) }}</el-descriptions-item>
          </el-descriptions>
          <el-descriptions title="KYB Documents" :column="1" border style="margin-top: 16px">
            <el-descriptions-item v-for="(path, docId) in kybDocuments" :key="docId" :label="docId">
              <div class="doc-preview">
                <el-image
                  v-if="isImagePath(path)"
                  :src="mediaUrl(path)"
                  :preview-src-list="[mediaUrl(path)]"
                  fit="contain"
                  class="doc-thumb"
                  preview-teleported
                />
                <span class="doc-path">{{ path }}</span>
                <el-button link type="primary" @click="downloadDoc(path, docId)">Download</el-button>
              </div>
            </el-descriptions-item>
          </el-descriptions>
        </template>
        <el-descriptions v-else title="Settlement" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="Bank">{{ dash(finance.bank_name) }}</el-descriptions-item>
          <el-descriptions-item label="Account name">{{ dash(finance.account_name) }}</el-descriptions-item>
          <el-descriptions-item label="Account number">{{ dash(finance.bank_account) }}</el-descriptions-item>
          <el-descriptions-item label="SWIFT">{{ dash(finance.swift_code) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="Submission Documents" :column="1" border style="margin-top: 16px">
          <el-descriptions-item label="Business License">
            <div v-if="images.license_image" class="doc-preview">
              <el-image
                :src="mediaUrl(images.license_image)"
                :preview-src-list="[mediaUrl(images.license_image)]"
                fit="contain"
                class="doc-thumb"
                preview-teleported
              />
              <el-button link type="primary" @click="downloadDoc(images.license_image, 'business-license')">Download</el-button>
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item label="Legal Rep. ID Front">
            <div v-if="images.id_front_image" class="doc-preview">
              <el-image
                :src="mediaUrl(images.id_front_image)"
                :preview-src-list="[mediaUrl(images.id_front_image)]"
                fit="contain"
                class="doc-thumb"
                preview-teleported
              />
              <el-button link type="primary" @click="downloadDoc(images.id_front_image, 'legal-rep-id-front')">Download</el-button>
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item label="Legal Rep. ID Back">
            <div v-if="images.id_back_image" class="doc-preview">
              <el-image
                :src="mediaUrl(images.id_back_image)"
                :preview-src-list="[mediaUrl(images.id_back_image)]"
                fit="contain"
                class="doc-thumb"
                preview-teleported
              />
              <el-button link type="primary" @click="downloadDoc(images.id_back_image, 'legal-rep-id-back')">Download</el-button>
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <div v-if="canReview(detailUser) && !isAgentQueue" class="decision-form">
          <div class="decision-title">Decision</div>
          <el-form label-position="top">
            <el-form-item label="Risk level" required>
              <el-select v-model="decision.risk_level" style="width: 100%">
                <el-option label="Low" value="LOW" />
                <el-option label="Medium" value="MEDIUM" />
                <el-option label="High" value="HIGH" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="decision.enable_wire_transfer">Enable wire transfer</el-checkbox>
            </el-form-item>
            <el-form-item label="Fee model" required>
              <el-select v-model="decision.fee_model" style="width: 100%">
                <el-option label="Percentage" value="PERCENTAGE" />
                <el-option label="Fixed" value="FIXED" />
                <el-option label="Tiered" value="TIERED" />
              </el-select>
            </el-form-item>
            <el-form-item label="Fee rate" required>
              <el-input v-model="decision.fee_rate" />
            </el-form-item>
            <el-form-item label="Fixed fee">
              <el-input v-model="decision.fixed_fee" />
            </el-form-item>
            <el-form-item label="Minimum fee">
              <el-input v-model="decision.min_fee" />
            </el-form-item>
            <el-form-item label="Single limit">
              <el-input v-model="decision.max_single_amount" />
            </el-form-item>
            <el-form-item label="Daily limit">
              <el-input v-model="decision.daily_limit" />
            </el-form-item>
            <el-form-item label="Remark">
              <el-input v-model="decision.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <div class="decision-actions">
            <el-button type="danger" @click="submitReject">Reject</el-button>
            <el-button type="primary" :disabled="!canAgree" :loading="submitting" @click="submitAgree">Agree</el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import EmptyState from '@/components/EmptyState.vue'
import { getOnboardingList, getOnboardingDetail, reviewOnboarding, startOnboardingReview } from '@/api/userPortal'
import { reviewMerchantKyc } from '@/api/merchants'
import { formatDate, unwrapList, mediaUrl, downloadMedia } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const props = defineProps({
  embedded: { type: Boolean, default: false },
  portalRole: { type: String, default: 'merchant' }
})

const auth = useAuthStore()
const isAgentQueue = computed(() => props.portalRole === 'agent')
const canApprove = computed(() => (
  isAgentQueue.value
    ? auth.hasPermission('feature:agents.approve')
    : auth.hasPermission('feature:merchants.approve')
))
const pageTitle = computed(() => (isAgentQueue.value ? 'Agent onboarding' : 'KYC'))
const pageSubtitle = computed(() => (
  isAgentQueue.value
    ? 'Review agent KYB and agree to activate the agent'
    : 'Review merchant KYB, set risk, product and fee, then agree'
))

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const submitting = ref(false)
const filters = reactive({ search: '', stage: 'needs_review' })
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailUser = ref(null)
const basic = reactive({
  legal_name: '',
  id_type: '',
  id_number: '',
  contact_phone: '',
  nationality: '',
  address: '',
  license_expiry_date: ''
})
const finance = reactive({
  bank_name: '',
  branch_name: '',
  account_name: '',
  bank_account: '',
  swift_code: ''
})
const images = reactive({
  license_image: '',
  id_front_image: '',
  id_back_image: ''
})
const kyb = reactive({})
const applicationRef = ref('')
const decision = reactive({
  remark: '',
  risk_level: 'MEDIUM',
  enable_wire_transfer: true,
  fee_model: 'PERCENTAGE',
  fee_rate: '0.003',
  fixed_fee: '0',
  min_fee: '0',
  max_single_amount: '',
  daily_limit: '',
  kyc_tier: 'TIER_1',
  commission_rate: 0
})
const kpis = computed(() => [
  { label: 'Pending Profile', value: stats.value.pending_profile ?? 0, icon: 'Clock', bg: '#fff3e8', color: '#f08040' },
  { label: 'Approved', value: stats.value.approved ?? 0, icon: 'CircleCheck', bg: '#e9f8ef', color: '#67c23a' },
  { label: 'Rejected', value: stats.value.rejected ?? 0, icon: 'CircleClose', bg: '#fdecee', color: '#d0021b' }
])

const detailTitle = computed(() => {
  const name = detailUser.value?.username || ''
  const prefix = isAgentQueue.value ? 'Agent onboarding' : 'KYC'
  return name ? `${prefix} — ${name}` : prefix
})

const hasKyb = computed(() => Object.keys(kyb).length > 0)
const kybPeople = computed(() => (Array.isArray(kyb.people) ? kyb.people : []))
const kybDocuments = computed(() => kyb.kyb_documents || {})

const canAgree = computed(() => {
  if (!canApprove.value) return false
  if (isAgentQueue.value) return true
  return Boolean(decision.risk_level && decision.fee_model && String(decision.fee_rate ?? '').trim() !== '' && decision.enable_wire_transfer)
})

function isProfilePending(row) {
  const status = row?.onboarding_status || row?.status
  return status === 'pending' || status === 'under_review'
}

function isKycPending(row) {
  return (row?.onboarding_status || row?.status) === 'approved' && row?.merchant_kyc_status === 'PENDING'
}

function canReview(row) {
  return Boolean(row) && canApprove.value && (isProfilePending(row) || isKycPending(row))
}

function dash(value) {
  return value || '—'
}

function isImagePath(path) {
  return /\.(png|jpe?g|gif|webp|bmp)$/i.test(String(path || ''))
}

function downloadDoc(path, filename) {
  const ext = path.split('.').pop()?.split('?')[0] || 'png'
  const base = filename || path.split('/').pop() || 'document'
  downloadMedia(path, base.includes('.') ? base : `${base}.${ext}`)
}

function patchRow(id, patch) {
  const idx = rows.value.findIndex((r) => r.id === id)
  if (idx !== -1) Object.assign(rows.value[idx], patch)
  if (detailUser.value?.id === id) Object.assign(detailUser.value, patch)
}

function resetDecision(defaults = {}) {
  Object.assign(decision, {
    remark: '',
    risk_level: defaults.risk_level || 'MEDIUM',
    enable_wire_transfer: defaults.enable_wire_transfer !== false,
    fee_model: defaults.fee_model || 'PERCENTAGE',
    fee_rate: defaults.fee_rate ?? '0.003',
    fixed_fee: defaults.fixed_fee ?? '0',
    min_fee: defaults.min_fee ?? '0',
    max_single_amount: defaults.max_single_amount || '',
    daily_limit: defaults.daily_limit || '',
    kyc_tier: defaults.kyc_tier || 'TIER_1',
    commission_rate: defaults.commission_rate === undefined || defaults.commission_rate === ''
      ? 0
      : Number(defaults.commission_rate)
  })
}

async function load() {
  loading.value = true
  try {
    const data = await getOnboardingList({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      stage: filters.stage || 'needs_review',
      portal_role: props.portalRole || 'merchant'
    })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
    stats.value = data.stats || {}
  } finally {
    loading.value = false
  }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }

async function agreeFromList(row) {
  detailUser.value = row
  await submitAgree()
}

async function rejectFromList(row) {
  detailUser.value = row
  await submitReject()
}

async function openDetail(row) {
  detailUser.value = row
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(basic, {
    legal_name: '', id_type: '', id_number: '', contact_phone: '',
    nationality: '', address: '', license_expiry_date: ''
  })
  Object.assign(finance, { bank_name: '', branch_name: '', account_name: '', bank_account: '', swift_code: '' })
  Object.assign(images, { license_image: '', id_front_image: '', id_back_image: '' })
  Object.keys(kyb).forEach((k) => delete kyb[k])
  applicationRef.value = ''
  resetDecision()
  try {
    if ((row.onboarding_status || row.status) === 'pending') {
      const started = await startOnboardingReview(row.id)
      patchRow(row.id, {
        onboarding_status: started.onboarding_status || started.status || 'under_review',
        status: started.onboarding_status || started.status || 'under_review'
      })
    }
    const data = await getOnboardingDetail(row.id)
    const payload = data?.data || {}
    Object.assign(basic, payload.basic || {})
    Object.assign(finance, payload.finance || {})
    Object.assign(images, payload.images || {})
    Object.assign(kyb, payload.kyb || {})
    applicationRef.value = payload.application_ref || kyb.application_ref || ''
    resetDecision(data?.decision_defaults || {})
  } finally {
    detailLoading.value = false
  }
}

function merchantDecisionPayload() {
  const payload = {
    risk_level: decision.risk_level,
    enable_wire_transfer: Boolean(decision.enable_wire_transfer),
    fee_model: decision.fee_model,
    fee_rate: decision.fee_rate,
    fixed_fee: decision.fixed_fee || '0',
    min_fee: decision.min_fee || '0'
  }
  if (decision.max_single_amount) payload.max_single_amount = decision.max_single_amount
  if (decision.daily_limit) payload.daily_limit = decision.daily_limit
  return payload
}

async function submitAgree() {
  const row = detailUser.value
  if (!row || !canAgree.value) return
  submitting.value = true
  try {
    if (isKycPending(row) && !isProfilePending(row)) {
      await reviewKyc(row, 'approve')
      return
    }
    const payload = isAgentQueue.value
      ? {
          action: 'approve',
          remark: decision.remark || ''
        }
      : {
          action: 'approve',
          remark: decision.remark || '',
          ...merchantDecisionPayload()
        }
    const result = await reviewOnboarding(row.id, payload)
    ElMessage.success('The application has been approved.')
    patchRow(row.id, {
      onboarding_status: result.status,
      status: result.status,
      merchant_no: result.merchant_no || row.merchant_no || '',
      merchant_status: result.merchant_status || '',
      merchant_kyc_status: result.merchant_kyc_status || '',
      agent_no: result.agent_no || row.agent_no || '',
      agent_status: result.agent_status || '',
      agent_kyc_status: result.agent_kyc_status || '',
      portal_role: result.portal_role || row.portal_role || '',
      next_stage: result.next_stage || ''
    })
    detailVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

async function submitReject() {
  const row = detailUser.value
  if (!row) return
  let remark = (decision.remark || '').trim()
  if (!remark) {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', {
      inputPattern: /.+/,
      inputErrorMessage: 'A rejection reason is required.'
    })
    remark = value
  }
  submitting.value = true
  try {
    if (isKycPending(row) && !isProfilePending(row)) {
      await reviewKyc(row, 'reject', remark)
      return
    }
    const result = await reviewOnboarding(row.id, { action: 'reject', remark })
    ElMessage.success('The application has been rejected.')
    patchRow(row.id, {
      onboarding_status: result.status,
      status: result.status,
      next_stage: result.next_stage || ''
    })
    detailVisible.value = false
    load()
  } finally {
    submitting.value = false
  }
}

async function reviewKyc(row, action, reason = '') {
  if (!row?.merchant_no) return
  if (action === 'reject' && !reason) {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    reason = value
  }
  const payload = action === 'reject'
    ? { action, reason }
    : { action, reason, ...merchantDecisionPayload() }
  const result = await reviewMerchantKyc(row.merchant_no, payload)
  ElMessage.success(action === 'approve' ? 'The application has been approved.' : 'The application has been rejected.')
  patchRow(row.id, {
    merchant_kyc_status: result.kyc_status,
    merchant_status: result.merchant_status || (action === 'approve' ? 'ACTIVE' : row.merchant_status)
  })
  detailVisible.value = false
  load()
}

onMounted(load)
</script>

<style scoped>
.doc-preview {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.doc-thumb {
  max-width: 100%;
  max-height: 160px;
  cursor: pointer;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.doc-path {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
}
.decision-form {
  width: 100%;
  text-align: left;
}
.decision-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.decision-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
