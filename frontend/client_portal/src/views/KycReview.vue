<template>
  <div>
    <PageHeader v-if="!embedded" title="KYC" subtitle="Review onboarding documentation and approve KYC" />
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
        <el-table-column label="Role" width="110">
          <template #default="{ row }">{{ row.portal_role === 'agent' ? 'Agent' : 'Customer' }}</template>
        </el-table-column>
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
        <el-table-column label="Actions" min-width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">View</el-button>
            <el-button v-if="canReview(row)" link type="success" @click="reviewApplication(row, 'approve')">Approve</el-button>
            <el-button v-if="canReview(row)" link type="danger" @click="reviewApplication(row, 'reject')">Reject</el-button>
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
          <el-descriptions-item label="Role">{{ detailUser?.portal_role === 'agent' ? 'Agent' : 'Customer' }}</el-descriptions-item>
          <el-descriptions-item label="Legal Name">{{ dash(basic.legal_name) }}</el-descriptions-item>
          <el-descriptions-item label="ID Type">{{ dash(basic.id_type) }}</el-descriptions-item>
          <el-descriptions-item label="ID Number">{{ dash(basic.id_number) }}</el-descriptions-item>
          <el-descriptions-item label="Phone">{{ dash(basic.contact_phone) }}</el-descriptions-item>
          <el-descriptions-item label="Nationality">{{ dash(basic.nationality) }}</el-descriptions-item>
          <el-descriptions-item label="Address">{{ dash(basic.address) }}</el-descriptions-item>
          <el-descriptions-item v-if="ENABLE_AGENTS" label="Agent Code">{{ dash(basic.agent_code) }}</el-descriptions-item>
          <el-descriptions-item label="Licence Expiry">{{ dash(basic.license_expiry_date) }}</el-descriptions-item>
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
import { ENABLE_AGENTS } from '@/config/features'
import { useAuthStore } from '@/store/auth'

defineProps({
  embedded: { type: Boolean, default: false },
})

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:merchants.approve'))

const KYC_APPROVE_DEFAULTS = {
  risk_level: 'MEDIUM',
  fee_model: 'PERCENTAGE',
  fee_rate: '0.003',
  fixed_fee: '0',
  min_fee: '0'
}

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
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
  agent_code: '',
  license_expiry_date: ''
})
const images = reactive({
  license_image: '',
  id_front_image: '',
  id_back_image: ''
})
const kpis = computed(() => [
  { label: 'Pending Profile', value: stats.value.pending_profile ?? 0, icon: 'Clock', bg: '#fff3e8', color: '#f08040' },
  { label: 'Approved', value: stats.value.approved ?? 0, icon: 'CircleCheck', bg: '#e9f8ef', color: '#67c23a' },
  { label: 'Rejected', value: stats.value.rejected ?? 0, icon: 'CircleClose', bg: '#fdecee', color: '#d0021b' }
])

const detailTitle = computed(() => {
  const name = detailUser.value?.username || ''
  return name ? `KYC — ${name}` : 'KYC'
})

function isProfilePending(row) {
  const status = row?.onboarding_status || row?.status
  return status === 'pending' || status === 'under_review'
}

function isKycPending(row) {
  return (row?.onboarding_status || row?.status) === 'approved' && row?.merchant_kyc_status === 'PENDING'
}

function canReview(row) {
  return canApprove.value && (isProfilePending(row) || isKycPending(row))
}

function dash(value) {
  return value || '—'
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

async function load() {
  loading.value = true
  try {
    const data = await getOnboardingList({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      stage: filters.stage || 'needs_review'
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

async function openDetail(row) {
  detailUser.value = row
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(basic, {
    legal_name: '', id_type: '', id_number: '', contact_phone: '',
    nationality: '', address: '', agent_code: '', license_expiry_date: ''
  })
  Object.assign(images, { license_image: '', id_front_image: '', id_back_image: '' })
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
    Object.assign(images, payload.images || {})
  } finally {
    detailLoading.value = false
  }
}

async function reviewApplication(row, action) {
  if (isKycPending(row) && !isProfilePending(row)) {
    await reviewKyc(row, action)
    return
  }
  await reviewProfile(row, action)
}

async function reviewProfile(row, action) {
  let remark = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    remark = value
  }
  const result = await reviewOnboarding(row.id, { action, remark })
  ElMessage.success(action === 'approve' ? 'The application has been approved.' : 'The application has been rejected.')
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
}

async function reviewKyc(row, action) {
  if (!row?.merchant_no) return
  let reason = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
    reason = value
  }
  const payload = action === 'reject'
    ? { action, reason }
    : { action, ...KYC_APPROVE_DEFAULTS }
  const result = await reviewMerchantKyc(row.merchant_no, payload)
  ElMessage.success(action === 'approve' ? 'The application has been approved.' : 'The application has been rejected.')
  patchRow(row.id, {
    merchant_kyc_status: result.kyc_status,
    merchant_status: result.merchant_status || (action === 'approve' ? 'ACTIVE' : row.merchant_status)
  })
  if (detailUser.value?.id === row.id) detailVisible.value = false
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
</style>
