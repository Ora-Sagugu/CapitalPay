<template>
  <div class="page-card">
    <template v-if="!isSummaryMode">
      <div class="onboarding-wizard">
        <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 24px">
          <el-step :title="$t('onboarding.basic')" />
          <el-step v-if="!isAgent" :title="$t('onboarding.finance')" />
          <el-step :title="$t('onboarding.docs')" />
        </el-steps>

        <el-form v-if="step === 0" :model="basic" label-width="140px" style="max-width: 640px">
          <el-form-item :label="$t('onboarding.legalName')" required>
            <el-input v-model="basic.legal_name" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.idType')" required>
            <el-select v-model="basic.id_type" style="width: 100%">
              <el-option :label="$t('onboarding.idTypes.id_card')" value="id_card" />
              <el-option :label="$t('onboarding.idTypes.passport')" value="passport" />
              <el-option :label="$t('onboarding.idTypes.business_license')" value="business_license" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('onboarding.idNumber')" required>
            <el-input v-model="basic.id_number" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.phone')" required>
            <el-input v-model="basic.contact_phone" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.nationality')">
            <el-input v-model="basic.nationality" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.address')">
            <el-input v-model="basic.address" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item v-if="ENABLE_AGENTS && !isAgent" :label="$t('onboarding.agentCode')">
            <el-input v-model="basic.agent_code" />
          </el-form-item>
          <el-form-item
            v-if="ENABLE_AGENTS && !isAgent && basic.agent_name"
            :label="$t('onboarding.agentName')"
          >
            <el-input :model-value="basic.agent_name" disabled />
          </el-form-item>
          <el-form-item :label="$t('onboarding.licenceExpiry')">
            <el-date-picker
              v-model="basic.license_expiry_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>

        <el-form
          v-else-if="!isAgent && step === 1"
          :model="finance"
          label-width="140px"
          style="max-width: 640px"
        >
          <el-form-item :label="$t('onboarding.bankName')" required>
            <el-input v-model="finance.bank_name" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.branchName')">
            <el-input v-model="finance.branch_name" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.accountName')" required>
            <el-input v-model="finance.account_name" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.accountNo')" required>
            <el-input v-model="finance.bank_account" />
          </el-form-item>
          <el-form-item :label="$t('onboarding.swift')">
            <el-input v-model="finance.swift_code" />
          </el-form-item>
        </el-form>

        <el-form v-else :model="images" class="docs-form" label-width="200px" style="max-width: 720px">
          <el-form-item :label="$t('onboarding.license')" required>
            <el-upload :show-file-list="false" :http-request="(opt) => upload(opt, 'license_image')">
              <el-button>{{ $t('onboarding.upload') }}</el-button>
            </el-upload>
            <div class="path">{{ images.license_image || $t('onboarding.notUploaded') }}</div>
          </el-form-item>
          <el-form-item label=" ">
            <p class="docs-hint">{{ $t('onboarding.docsHint') }}</p>
          </el-form-item>
          <el-form-item :label="$t('onboarding.idFront')" required>
            <el-upload :show-file-list="false" :http-request="(opt) => upload(opt, 'id_front_image')">
              <el-button>{{ $t('onboarding.upload') }}</el-button>
            </el-upload>
            <div class="path">{{ images.id_front_image || $t('onboarding.notUploaded') }}</div>
          </el-form-item>
          <el-form-item :label="$t('onboarding.idBack')" required>
            <el-upload :show-file-list="false" :http-request="(opt) => upload(opt, 'id_back_image')">
              <el-button>{{ $t('onboarding.upload') }}</el-button>
            </el-upload>
            <div class="path">{{ images.id_back_image || $t('onboarding.notUploaded') }}</div>
          </el-form-item>
        </el-form>

        <div class="actions">
          <el-button v-if="step > 0" @click="step -= 1">{{ $t('onboarding.previous') }}</el-button>
          <el-button v-if="step < lastStep" type="primary" @click="nextStep">{{ $t('onboarding.next') }}</el-button>
          <el-button
            v-if="step === lastStep"
            type="primary"
            :loading="submitting"
            @click="submit"
          >
            {{ $t('onboarding.submit') }}
          </el-button>
          <el-button @click="loadStatus">{{ $t('onboarding.refresh') }}</el-button>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="onboarding-summary">
        <h3 class="section-title">{{ $t('onboarding.progressTitle') }}</h3>
        <el-timeline class="onboarding-timeline">
          <el-timeline-item
            v-for="item in progressSteps"
            :key="item.code"
            :timestamp="item.at ? formatTime(item.at) : ''"
            :type="item.verified ? 'success' : (item.active ? 'primary' : 'info')"
            :hollow="!item.verified && !item.active"
          >
            <div>{{ item.title }}</div>
            <div v-if="item.detail" class="timeline-detail">{{ item.detail }}</div>
          </el-timeline-item>
        </el-timeline>

        <h3 class="section-title">{{ $t('onboarding.profileTitle') }}</h3>
        <el-descriptions :column="1" border size="small" class="detail-block">
          <el-descriptions-item :label="$t('onboarding.legalName')">
            {{ displayValue(basic.legal_name) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idType')">
            {{ idTypeLabel(basic.id_type) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idNumber')">
            {{ maskTail(basic.id_number) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.phone')">
            {{ displayValue(basic.contact_phone) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="basic.nationality" :label="$t('onboarding.nationality')">
            {{ basic.nationality }}
          </el-descriptions-item>
          <el-descriptions-item v-if="basic.address" :label="$t('onboarding.address')">
            {{ basic.address }}
          </el-descriptions-item>
        </el-descriptions>

        <template v-if="ENABLE_AGENTS && !isAgent">
          <h3 class="section-title">{{ $t('onboarding.agentTitle') }}</h3>
          <el-descriptions :column="1" border size="small" class="detail-block">
            <el-descriptions-item :label="$t('onboarding.agentCode')">
              {{ displayValue(basic.agent_code) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.agentName')">
              {{ displayValue(basic.agent_name) }}
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <template v-if="!isAgent">
          <h3 class="section-title">{{ $t('onboarding.financeTitle') }}</h3>
          <el-descriptions :column="1" border size="small" class="detail-block">
            <el-descriptions-item :label="$t('onboarding.bankName')">
              {{ displayValue(finance.bank_name) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="finance.branch_name" :label="$t('onboarding.branchName')">
              {{ finance.branch_name }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.accountName')">
              {{ displayValue(finance.account_name) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.accountNo')">
              {{ maskTail(finance.bank_account) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="finance.swift_code" :label="$t('onboarding.swift')">
              {{ finance.swift_code }}
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <h3 class="section-title">{{ $t('onboarding.docsTitle') }}</h3>
        <el-descriptions :column="1" border size="small" class="detail-block">
          <el-descriptions-item :label="$t('onboarding.license')">
            <div class="doc-cell">
              <img
                v-if="images.license_image"
                class="doc-thumb"
                :src="docUrl(images.license_image)"
                :alt="$t('onboarding.license')"
              >
              <span>{{ images.license_image ? $t('onboarding.uploaded') : $t('onboarding.notUploaded') }}</span>
            </div>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idFront')">
            <div class="doc-cell">
              <img
                v-if="images.id_front_image"
                class="doc-thumb"
                :src="docUrl(images.id_front_image)"
                :alt="$t('onboarding.idFront')"
              >
              <span>{{ images.id_front_image ? $t('onboarding.uploaded') : $t('onboarding.notUploaded') }}</span>
            </div>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('onboarding.idBack')">
            <div class="doc-cell">
              <img
                v-if="images.id_back_image"
                class="doc-thumb"
                :src="docUrl(images.id_back_image)"
                :alt="$t('onboarding.idBack')"
              >
              <span>{{ images.id_back_image ? $t('onboarding.uploaded') : $t('onboarding.notUploaded') }}</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>

        <div class="actions">
          <el-button @click="loadStatus">{{ $t('onboarding.refresh') }}</el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getOnboardingStatus, submitOnboarding, uploadOnboardingFile } from '@/api/onboarding'
import { useAuthStore } from '@/store/auth'
import { datetime } from '@/utils/format'
import { ENABLE_AGENTS } from '@/config/features'

const { t } = useI18n()
const auth = useAuthStore()
const isAgent = computed(() => auth.isAgent)
const lastStep = computed(() => (isAgent.value ? 1 : 2))
const step = ref(0)
const submitting = ref(false)
const statusInfo = reactive({
  onboarding_status: 'none',
  submitted_at: null,
  reviewed_at: null,
  reviewer: '',
  remark: '',
  agent_review_status: 'none',
  agent_reviewed_at: null,
  agent_reviewer: '',
  agent_remark: '',
  data: null
})

const basic = reactive({
  legal_name: '',
  id_type: 'id_card',
  id_number: '',
  contact_phone: '',
  nationality: '',
  address: '',
  agent_code: '',
  agent_name: '',
  license_expiry_date: null
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

const isSummaryMode = computed(() =>
  ['pending', 'under_review', 'approved'].includes(statusInfo.onboarding_status)
)

const hasAgentGate = computed(() => {
  const s = statusInfo.agent_review_status
  return !!s && s !== 'none'
})

const progressSteps = computed(() => {
  const status = statusInfo.onboarding_status
  const submitted = !!statusInfo.submitted_at
  const reviewed = !!statusInfo.reviewed_at
  const agentStatus = statusInfo.agent_review_status
  if (hasAgentGate.value) {
    const agentDone = agentStatus === 'approved' || agentStatus === 'rejected'
    let agentTitle = t('onboarding.progress.waitingAgent')
    if (agentStatus === 'approved') agentTitle = t('onboarding.progress.agentApproved')
    if (agentStatus === 'rejected') agentTitle = t('onboarding.progress.agentRejected')
    const agentParts = []
    if (statusInfo.agent_reviewer) agentParts.push(`${t('onboarding.reviewer')}: ${statusInfo.agent_reviewer}`)
    if (statusInfo.agent_remark) agentParts.push(`${t('onboarding.remarks')}: ${statusInfo.agent_remark}`)
    const opsStarted = status === 'under_review' || reviewed || status === 'approved'
    let opsTitle = t('onboarding.progress.waitingOps')
    if (status === 'under_review' || opsStarted) opsTitle = t('onboarding.progress.opsReview')
    if (agentStatus !== 'approved') opsTitle = t('onboarding.progress.opsReview')
    let decisionTitle = t('onboarding.progress.awaitingDecision')
    if (status === 'approved') decisionTitle = t('onboarding.progress.approved')
    if (status === 'rejected' && agentStatus !== 'rejected') decisionTitle = t('onboarding.progress.rejected')
    const decisionParts = []
    if (statusInfo.reviewer) decisionParts.push(`${t('onboarding.reviewer')}: ${statusInfo.reviewer}`)
    if (statusInfo.remark) decisionParts.push(`${t('onboarding.remarks')}: ${statusInfo.remark}`)
    return [
      {
        code: 'submitted',
        title: t('onboarding.progress.submitted'),
        at: statusInfo.submitted_at,
        verified: submitted,
        active: false
      },
      {
        code: 'agent_review',
        title: agentTitle,
        at: statusInfo.agent_reviewed_at,
        detail: agentParts.join(' · '),
        verified: agentDone,
        active: agentStatus === 'pending'
      },
      {
        code: 'ops_review',
        title: opsTitle,
        at: null,
        verified: opsStarted,
        active: agentStatus === 'approved' && (status === 'pending' || status === 'under_review') && !reviewed
      },
      {
        code: 'decision',
        title: decisionTitle,
        at: statusInfo.reviewed_at,
        detail: decisionParts.join(' · '),
        verified: reviewed && agentStatus !== 'rejected',
        active: status === 'approved' || (status === 'rejected' && agentStatus === 'approved')
      }
    ]
  }
  const underReview = status === 'under_review' || reviewed || status === 'approved' || status === 'rejected'
  let decisionTitle = t('onboarding.progress.awaitingDecision')
  if (status === 'approved') decisionTitle = t('onboarding.progress.approved')
  if (status === 'rejected') decisionTitle = t('onboarding.progress.rejected')
  const decisionParts = []
  if (statusInfo.reviewer) decisionParts.push(`${t('onboarding.reviewer')}: ${statusInfo.reviewer}`)
  if (statusInfo.remark) decisionParts.push(`${t('onboarding.remarks')}: ${statusInfo.remark}`)
  return [
    {
      code: 'submitted',
      title: t('onboarding.progress.submitted'),
      at: statusInfo.submitted_at,
      verified: submitted,
      active: status === 'pending' && !reviewed
    },
    {
      code: 'under_review',
      title: t('onboarding.progress.underReview'),
      at: null,
      verified: underReview,
      active: status === 'under_review'
    },
    {
      code: 'decision',
      title: decisionTitle,
      at: statusInfo.reviewed_at,
      detail: decisionParts.join(' · '),
      verified: reviewed,
      active: status === 'approved' || status === 'rejected'
    }
  ]
})

function formatTime(value) {
  return datetime(value)
}

function displayValue(value) {
  return value || '—'
}

function maskTail(value) {
  const s = String(value || '')
  if (!s) return '—'
  if (s.length <= 4) return s
  return `****${s.slice(-4)}`
}

function idTypeLabel(code) {
  if (!code) return '—'
  const key = `onboarding.idTypes.${code}`
  const label = t(key)
  return label === key ? code : label
}

function docUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path) || path.startsWith('/') || path.startsWith('data:')) return path
  return `/media/${path}`
}

function fillFromData(data) {
  if (!data) return
  const b = data.basic || {}
  const f = data.finance || {}
  const i = data.images || {}
  Object.assign(basic, {
    legal_name: b.legal_name || '',
    id_type: b.id_type || 'id_card',
    id_number: b.id_number || '',
    contact_phone: b.contact_phone || '',
    nationality: b.nationality || '',
    address: b.address || '',
    agent_code: b.agent_code || '',
    agent_name: b.agent_name || '',
    license_expiry_date: b.license_expiry_date || null
  })
  Object.assign(finance, {
    bank_name: f.bank_name || '',
    branch_name: f.branch_name || '',
    account_name: f.account_name || '',
    bank_account: f.bank_account || '',
    swift_code: f.swift_code || ''
  })
  Object.assign(images, {
    license_image: i.license_image || '',
    id_front_image: i.id_front_image || '',
    id_back_image: i.id_back_image || ''
  })
}

async function loadStatus() {
  const res = await getOnboardingStatus()
  Object.assign(statusInfo, {
    onboarding_status: res.onboarding_status,
    submitted_at: res.submitted_at,
    reviewed_at: res.reviewed_at,
    reviewer: res.reviewer,
    remark: res.remark,
    agent_review_status: res.agent_review_status || 'none',
    agent_reviewed_at: res.agent_reviewed_at || null,
    agent_reviewer: res.agent_reviewer || '',
    agent_remark: res.agent_remark || '',
    data: res.data
  })
  fillFromData(res.data)
  if (auth.user) {
    auth.user.onboarding_status = res.onboarding_status
    localStorage.setItem('user', JSON.stringify(auth.user))
  }
}

function validateStep() {
  if (step.value === 0) {
    if (!basic.legal_name || !basic.id_type || !basic.id_number || !basic.contact_phone) {
      ElMessage.warning(t('onboarding.validateBasic'))
      return false
    }
    return true
  }
  if (!isAgent.value && step.value === 1) {
    if (!finance.bank_name || !finance.account_name || !finance.bank_account) {
      ElMessage.warning(t('onboarding.validateFinance'))
      return false
    }
    return true
  }
  if (!images.license_image || !images.id_front_image || !images.id_back_image) {
    ElMessage.warning(t('onboarding.validateDocs'))
    return false
  }
  return true
}

function nextStep() {
  if (!validateStep()) return
  step.value += 1
}

async function upload(opt, field) {
  const data = await uploadOnboardingFile(opt.file)
  images[field] = data.path || data.url
  ElMessage.success(t('onboarding.uploadOk'))
}

async function submit() {
  if (!validateStep()) return
  submitting.value = true
  try {
    const basicPayload = { ...basic }
    delete basicPayload.agent_name
    const payload = {
      basic: basicPayload,
      images: { ...images }
    }
    if (!isAgent.value) {
      payload.finance = { ...finance }
    }
    await submitOnboarding(payload)
    ElMessage.success(t('onboarding.submitOk'))
    await loadStatus()
  } finally {
    submitting.value = false
  }
}

onMounted(loadStatus)
</script>
<style scoped>
.path { color: #8c8c8c; font-size: 12px; margin-top: 6px; word-break: break-all; }
.docs-form :deep(.el-form-item__label) {
  white-space: nowrap;
}
.docs-hint {
  margin: 0;
  color: #8c8c8c;
  font-size: 13px;
  line-height: 1.5;
}
.actions {
  margin-top: 24px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.section-title {
  margin: 20px 0 10px;
  font-size: 15px;
  font-weight: 600;
}
.detail-block { margin-bottom: 8px; }
.timeline-detail { color: #909399; font-size: 12px; margin-top: 4px; }
.doc-cell { display: flex; align-items: center; gap: 10px; }
.doc-thumb {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
</style>
