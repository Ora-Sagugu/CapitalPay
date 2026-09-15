<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.kycTitle') }}</h1>
    <p class="psub">{{ $t('agent.kycSub') }}</p>

    <el-alert
      v-if="auth.onboardingStatus !== 'approved'"
      :title="$t('agent.needOnboarding')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <div class="page-card">
      <div class="toolbar">
        <el-input
          v-model="filters.search"
          :placeholder="$t('agent.kycSearch')"
          clearable
          style="width: 260px"
          @keyup.enter="reload"
        />
        <el-select v-model="filters.stage" style="width: 180px" @change="reload">
          <el-option :label="$t('agent.kycNeedsReview')" value="needs_review" />
          <el-option :label="$t('agent.kycApproved')" value="approved" />
          <el-option :label="$t('agent.kycRejected')" value="rejected" />
        </el-select>
        <el-button @click="reload">{{ $t('common.refresh') }}</el-button>
        <span class="kpi">{{ $t('agent.kycPendingKpi') }} {{ stats.pending_profile ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.kycApproved') }} {{ stats.approved ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.kycRejected') }} {{ stats.rejected ?? 0 }}</span>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="username" :label="$t('agent.kycUsername')" min-width="150" />
        <el-table-column prop="email" :label="$t('agent.kycEmail')" min-width="200" />
        <el-table-column :label="$t('agent.kycLegalPerson')" min-width="150">
          <template #default="{ row }">{{ dash(row.legal_person) }}</template>
        </el-table-column>
        <el-table-column :label="$t('agent.kycIdType')" min-width="120">
          <template #default="{ row }">{{ idTypeLabel(row.id_type) }}</template>
        </el-table-column>
        <el-table-column :label="$t('agent.kycReviewStatus')" min-width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.agent_review_status)" size="small">
              {{ statusLabel(row.agent_review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('agent.kycSubmittedAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" min-width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ $t('agent.kycView') }}</el-button>
            <el-button
              v-if="row.agent_review_status === 'pending'"
              link
              type="success"
              @click="reviewApplication(row, 'approve')"
            >{{ $t('agent.kycApprove') }}</el-button>
            <el-button
              v-if="row.agent_review_status === 'pending'"
              link
              type="danger"
              @click="reviewApplication(row, 'reject')"
            >{{ $t('agent.kycReject') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.kycEmpty')" />
      <el-pagination
        v-if="total > pageSize"
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="640px">
      <div v-loading="detailLoading">
        <el-descriptions :title="$t('onboarding.profileTitle')" :column="1" border>
          <el-descriptions-item :label="$t('agent.kycUsername')">{{ dash(detailUser?.username) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.legalName')">{{ dash(basic.legal_name) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idType')">{{ idTypeLabel(basic.id_type) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idNumber')">{{ dash(basic.id_number) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.phone')">{{ dash(basic.contact_phone) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.nationality')">{{ dash(basic.nationality) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.address')">{{ dash(basic.address) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.licenceExpiry')">{{ dash(basic.license_expiry_date) }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions :title="$t('onboarding.docsTitle')" :column="1" border style="margin-top: 16px">
          <el-descriptions-item :label="$t('onboarding.license')">
            <div v-if="images.license_image" class="doc-preview">
              <el-image :src="mediaUrl(images.license_image)" :preview-src-list="[mediaUrl(images.license_image)]" fit="contain" class="doc-thumb" preview-teleported />
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idFront')">
            <div v-if="images.id_front_image" class="doc-preview">
              <el-image :src="mediaUrl(images.id_front_image)" :preview-src-list="[mediaUrl(images.id_front_image)]" fit="contain" class="doc-thumb" preview-teleported />
            </div>
            <span v-else>—</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idBack')">
            <div v-if="images.id_back_image" class="doc-preview">
              <el-image :src="mediaUrl(images.id_back_image)" :preview-src-list="[mediaUrl(images.id_back_image)]" fit="contain" class="doc-thumb" preview-teleported />
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
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { getAgentKycList, getAgentKycDetail, reviewAgentKyc } from '@/api/agent'
import { datetime } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
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
  legal_name: '', id_type: '', id_number: '', contact_phone: '',
  nationality: '', address: '', license_expiry_date: ''
})
const images = reactive({ license_image: '', id_front_image: '', id_back_image: '' })

const detailTitle = computed(() => {
  const name = detailUser.value?.username || ''
  return name ? `${t('agent.kycTitle')} — ${name}` : t('agent.kycTitle')
})

function dash(value) {
  return value || '—'
}

function mediaUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path) || path.startsWith('/') || path.startsWith('data:')) return path
  return `/media/${path}`
}

function idTypeLabel(code) {
  if (!code) return '—'
  const key = `onboarding.idTypes.${code}`
  const label = t(key)
  return label === key ? code : label
}

function statusLabel(code) {
  if (code === 'approved') return t('agent.kycStatusApproved')
  if (code === 'rejected') return t('agent.kycStatusRejected')
  return t('agent.kycStatusPending')
}

function statusType(code) {
  if (code === 'approved') return 'success'
  if (code === 'rejected') return 'danger'
  return 'warning'
}

function patchRow(id, patch) {
  const idx = rows.value.findIndex((r) => r.id === id)
  if (idx !== -1) Object.assign(rows.value[idx], patch)
}

async function load() {
  if (auth.onboardingStatus !== 'approved') {
    rows.value = []
    stats.value = {}
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await getAgentKycList({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      stage: filters.stage || 'needs_review'
    })
    rows.value = data.items || data.results || []
    total.value = data.total || data.count || 0
    stats.value = data.stats || {}
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
  detailUser.value = row
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(basic, {
    legal_name: '', id_type: '', id_number: '', contact_phone: '',
    nationality: '', address: '', license_expiry_date: ''
  })
  Object.assign(images, { license_image: '', id_front_image: '', id_back_image: '' })
  try {
    const data = await getAgentKycDetail(row.id)
    const payload = data?.data || {}
    Object.assign(basic, payload.basic || {})
    Object.assign(images, payload.images || {})
  } finally {
    detailLoading.value = false
  }
}

async function reviewApplication(row, action) {
  let remark = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt(
      t('agent.kycRejectPrompt'),
      t('agent.kycRejectTitle'),
      { inputPattern: /.+/, inputErrorMessage: t('agent.kycRejectRequired') }
    )
    remark = value
  }
  const result = await reviewAgentKyc(row.id, { action, remark })
  ElMessage.success(action === 'approve' ? t('agent.kycApprovedMsg') : t('agent.kycRejectedMsg'))
  patchRow(row.id, {
    agent_review_status: result.agent_review_status,
    onboarding_status: result.onboarding_status,
    agent_reviewed_at: result.agent_reviewed_at,
    agent_reviewer: result.agent_reviewer,
    agent_remark: result.agent_remark
  })
  if (filters.stage === 'needs_review') {
    rows.value = rows.value.filter((item) => item.id !== row.id)
    total.value = Math.max(0, total.value - 1)
    stats.value = {
      ...stats.value,
      pending_profile: Math.max(0, (stats.value.pending_profile || 1) - 1),
      approved: (stats.value.approved || 0) + (action === 'approve' ? 1 : 0),
      rejected: (stats.value.rejected || 0) + (action === 'reject' ? 1 : 0)
    }
  }
  if (detailUser.value?.id === row.id) detailVisible.value = false
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.kpi { color: #8c8c8c; font-size: 13px; }
.doc-preview { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.doc-thumb {
  max-width: 100%;
  max-height: 160px;
  cursor: pointer;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
</style>
