<template>
  <div class="onboarding-page">
    <template v-if="isSummaryMode">
      <div class="onboarding-shell">
        <h1 class="ptitle">{{ $t('onboarding.progressTitle') }}</h1>
        <p class="psub">{{ statusLabel }}</p>
        <div class="page-card onboarding-card">
          <el-alert
            :title="statusLabel"
            :type="statusInfo.onboarding_status === 'rejected' ? 'error' : 'info'"
            :description="statusInfo.remark || $t('onboarding.statusHint')"
            :closable="false"
            show-icon
            style="margin-bottom: 24px"
          />
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item :label="$t('onboarding.legalName')">{{ displayValue(basic.legal_name) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.idType')">{{ idTypeLabel(basic.id_type) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.idNumber')">{{ displayValue(basic.id_number) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.nationality')">{{ displayValue(basic.nationality) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.phone')">{{ displayValue(basic.contact_phone) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('profile.email')">{{ displayValue(email) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.address')">{{ displayValue(basic.address) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.tradingMarket')">{{ marketLabel(basic.trading_market) }}</el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.trn')">{{ displayValue(basic.trn) }}</el-descriptions-item>
            <el-descriptions-item v-if="!isAgent && basic.agent_code" :label="$t('onboarding.agentCode')">
              {{ basic.agent_code }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.governmentId')">
              {{ fileLabel(images.government_id_image) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.proofOfAddress')">
              {{ fileLabel(images.proof_of_address_image) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('onboarding.trnCertificate')">
              {{ fileLabel(images.trn_certificate_image) }}
            </el-descriptions-item>
          </el-descriptions>
          <div class="actions">
            <el-button @click="loadStatus" :loading="loading">{{ $t('onboarding.refresh') }}</el-button>
            <el-button v-if="statusInfo.onboarding_status === 'rejected'" type="primary" @click="editAgain">
              {{ $t('onboarding.editAgain') }}
            </el-button>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="onboarding-shell">
        <h1 class="ptitle">{{ $t('onboarding.formTitle') }}</h1>
        <p class="psub">{{ $t('onboarding.formSubtitle') }}</p>
        <div class="page-card onboarding-card">
          <el-form
            ref="formRef"
            :model="formModel"
            :rules="rules"
            label-position="top"
            class="onboarding-form"
            @submit.prevent
          >
            <el-form-item :label="$t('onboarding.legalName')" prop="legal_name">
              <el-input v-model="basic.legal_name" maxlength="128" size="large" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.idType')" prop="id_type">
              <el-select v-model="basic.id_type" style="width: 100%" size="large">
                <el-option v-for="(label, code) in idTypeOptions" :key="code" :label="label" :value="code" />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('onboarding.idNumber')" prop="id_number">
              <el-input v-model="basic.id_number" maxlength="128" size="large" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.nationality')" prop="nationality">
              <el-input v-model="basic.nationality" maxlength="64" size="large" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.phone')" prop="contact_phone">
              <el-input v-model="basic.contact_phone" maxlength="20" size="large" />
            </el-form-item>
            <el-form-item :label="$t('profile.email')">
              <el-input :model-value="email" disabled size="large" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.address')" prop="address">
              <el-input v-model="basic.address" type="textarea" :rows="3" maxlength="512" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.tradingMarket')" prop="trading_market">
              <el-select v-model="basic.trading_market" style="width: 100%" size="large" :placeholder="$t('onboarding.tradingMarketPh')">
                <el-option
                  v-for="opt in tradingMarkets"
                  :key="opt.code"
                  :label="opt.label"
                  :value="opt.code"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('onboarding.trn')" prop="trn">
              <el-input v-model="basic.trn" maxlength="64" size="large" :placeholder="$t('onboarding.trnPh')" />
            </el-form-item>
            <el-form-item v-if="!isAgent" :label="$t('onboarding.agentCode')" prop="agent_code">
              <el-input v-model="basic.agent_code" maxlength="64" size="large" />
            </el-form-item>
            <el-form-item :label="$t('onboarding.governmentId')" prop="government_id_image">
              <el-upload
                :show-file-list="false"
                :http-request="(opt) => uploadDoc('government_id_image', opt)"
              >
                <el-button size="large" :loading="uploading.government_id_image">{{ $t('onboarding.upload') }}</el-button>
              </el-upload>
              <div class="file-status">{{ fileStatus(images.government_id_image) }}</div>
              <div class="file-hint">{{ $t('onboarding.anyFileHint') }}</div>
            </el-form-item>
            <el-form-item :label="$t('onboarding.proofOfAddress')" prop="proof_of_address_image">
              <el-upload
                :show-file-list="false"
                :http-request="(opt) => uploadDoc('proof_of_address_image', opt)"
              >
                <el-button size="large" :loading="uploading.proof_of_address_image">{{ $t('onboarding.upload') }}</el-button>
              </el-upload>
              <div class="file-status">{{ fileStatus(images.proof_of_address_image) }}</div>
              <div class="file-hint">{{ $t('onboarding.anyFileHint') }}</div>
            </el-form-item>
            <el-form-item :label="$t('onboarding.trnCertificate')" prop="trn_certificate_image">
              <el-upload
                :show-file-list="false"
                :http-request="(opt) => uploadDoc('trn_certificate_image', opt)"
              >
                <el-button size="large" :loading="uploading.trn_certificate_image">{{ $t('onboarding.upload') }}</el-button>
              </el-upload>
              <div class="file-status">{{ fileStatus(images.trn_certificate_image) }}</div>
              <div class="file-hint">{{ $t('onboarding.anyFileHint') }}</div>
            </el-form-item>
            <el-form-item class="submit-row">
              <el-button type="primary" size="large" :loading="submitting" @click="onSubmit">{{ $t('onboarding.submit') }}</el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getOnboardingStatus, submitOnboarding, uploadOnboardingFile } from '@/api/onboarding'
import { useAuthStore } from '@/store/auth'

const POLL_MS = 15000

const TRADING_MARKETS = [
  { code: 'ZM', label: 'Zambia' },
  { code: 'TZ', label: 'Tanzania' },
  { code: 'NG', label: 'Nigeria' },
  { code: 'RW', label: 'Rwanda' },
  { code: 'UG', label: 'Uganda' },
  { code: 'ZA', label: 'South Africa' },
  { code: 'MZ', label: 'Mozambique' },
  { code: 'EU', label: 'European Union' },
  { code: 'US', label: 'United States' },
  { code: 'PH', label: 'Philippines' },
  { code: 'JM', label: 'Jamaica (Caribbean)' },
  { code: 'OTHER', label: "My country isn't listed" }
]

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const submitting = ref(false)
const forceEdit = ref(false)
const uploading = reactive({
  government_id_image: false,
  proof_of_address_image: false,
  trn_certificate_image: false
})

const isAgent = computed(() => auth.isAgent)
const email = computed(() => auth.user?.email || '')
const tradingMarkets = TRADING_MARKETS

const statusInfo = reactive({
  onboarding_status: 'none',
  submitted_at: null,
  reviewed_at: null,
  reviewer: '',
  remark: '',
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
  trading_market: '',
  trn: ''
})

const images = reactive({
  government_id_image: '',
  proof_of_address_image: '',
  trn_certificate_image: ''
})

const formModel = computed(() => ({
  ...basic,
  ...images
}))

const idTypeOptions = computed(() => ({
  id_card: t('onboarding.idTypes.id_card'),
  passport: t('onboarding.idTypes.passport'),
  business_license: t('onboarding.idTypes.business_license'),
  other: t('onboarding.idTypes.other')
}))

const requiredMsg = computed(() => t('onboarding.validateBasic'))

const rules = computed(() => {
  const base = {
    legal_name: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    id_type: [{ required: true, message: requiredMsg.value, trigger: 'change' }],
    id_number: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    nationality: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    contact_phone: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    address: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    trading_market: [{ required: true, message: requiredMsg.value, trigger: 'change' }],
    trn: [{ required: true, message: requiredMsg.value, trigger: 'blur' }],
    government_id_image: [{ required: true, message: t('onboarding.validateDocs'), trigger: 'change' }],
    proof_of_address_image: [{ required: true, message: t('onboarding.validateDocs'), trigger: 'change' }],
    trn_certificate_image: [{ required: true, message: t('onboarding.validateDocs'), trigger: 'change' }]
  }
  if (!isAgent.value) {
    base.agent_code = [{ required: true, message: t('onboarding.agentCodeRequired'), trigger: 'blur' }]
  }
  return base
})

const isSummaryMode = computed(() => {
  if (forceEdit.value) return false
  return ['pending', 'under_review'].includes(statusInfo.onboarding_status)
})

const statusLabel = computed(() => {
  const key = `onboarding.status.${statusInfo.onboarding_status}`
  const label = t(key)
  return label === key ? statusInfo.onboarding_status : label
})

function displayValue(value) {
  return value || '—'
}

function fileLabel(path) {
  return path ? t('onboarding.uploaded') : t('onboarding.notUploaded')
}

function fileStatus(path) {
  if (!path) return t('onboarding.notUploaded')
  const name = String(path).split('/').pop() || path
  return `${t('onboarding.uploaded')}: ${name}`
}

function idTypeLabel(code) {
  if (!code) return '—'
  const key = `onboarding.idTypes.${code}`
  const label = t(key)
  return label === key ? code : label
}

function marketLabel(code) {
  const found = TRADING_MARKETS.find((item) => item.code === code)
  return found?.label || displayValue(code)
}

function fillFromData(data) {
  if (!data) return
  const b = data.basic || {}
  const i = data.images || {}
  Object.assign(basic, {
    legal_name: b.legal_name || '',
    id_type: b.id_type || 'id_card',
    id_number: b.id_number || '',
    contact_phone: b.contact_phone || '',
    nationality: b.nationality || '',
    address: b.address || '',
    agent_code: b.agent_code || '',
    trading_market: b.trading_market || '',
    trn: b.trn || ''
  })
  Object.assign(images, {
    government_id_image: i.government_id_image || i.id_front_image || '',
    proof_of_address_image: i.proof_of_address_image || i.id_back_image || '',
    trn_certificate_image: i.trn_certificate_image || i.license_image || ''
  })
}

function editAgain() {
  forceEdit.value = true
}

let pollTimer = null
let statusRequest = null

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPollingIfNeeded() {
  stopPolling()
  const status = statusInfo.onboarding_status
  if (status === 'pending' || status === 'under_review') {
    pollTimer = setInterval(() => {
      loadStatus()
    }, POLL_MS)
  }
}

async function enterWorkspace() {
  statusInfo.onboarding_status = 'approved'
  stopPolling()
  await router.replace(auth.homeRoute())
}

async function uploadDoc(field, option) {
  const file = option?.file
  if (!file) return
  uploading[field] = true
  try {
    const data = await uploadOnboardingFile(file)
    images[field] = data.path || data.url || ''
    formRef.value?.validateField?.(field)
    ElMessage.success(t('onboarding.uploadOk'))
    option?.onSuccess?.(data)
  } catch (err) {
    option?.onError?.(err)
  } finally {
    uploading[field] = false
  }
}

async function loadStatus() {
  if (statusRequest) return statusRequest
  loading.value = true
  statusRequest = (async () => {
    const res = await getOnboardingStatus()
    Object.assign(statusInfo, {
      onboarding_status: res.onboarding_status,
      submitted_at: res.submitted_at,
      reviewed_at: res.reviewed_at,
      reviewer: res.reviewer,
      remark: res.remark,
      data: res.data
    })
    fillFromData(res.data)
    auth.mergeUser({ onboarding_status: res.onboarding_status })
    if (res.onboarding_status === 'approved') {
      await enterWorkspace()
      return
    }
    if (res.onboarding_status === 'rejected') {
      forceEdit.value = true
    }
    startPollingIfNeeded()
  })()
  try {
    await statusRequest
  } finally {
    statusRequest = null
    loading.value = false
  }
}

async function onSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const body = {
      basic: {
        legal_name: basic.legal_name.trim(),
        id_type: basic.id_type,
        id_number: basic.id_number.trim(),
        contact_phone: basic.contact_phone.trim(),
        nationality: basic.nationality.trim(),
        address: basic.address.trim(),
        agent_code: isAgent.value ? '' : basic.agent_code.trim(),
        trading_market: basic.trading_market,
        trn: basic.trn.trim()
      },
      images: {
        government_id_image: images.government_id_image,
        proof_of_address_image: images.proof_of_address_image,
        trn_certificate_image: images.trn_certificate_image
      }
    }
    await submitOnboarding(body)
    ElMessage.success(t('onboarding.submitOk'))
    forceEdit.value = false
    await loadStatus()
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await auth.fetchProfile()
  if (auth.onboardingStatus === 'approved') {
    await enterWorkspace()
    return
  }
  if (!basic.contact_phone && auth.user?.phone) {
    basic.contact_phone = auth.user.phone
  }
  await loadStatus()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.onboarding-page {
  min-height: calc(100vh - 96px);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.onboarding-shell {
  width: 100%;
  max-width: 640px;
  margin: 0 auto;
  padding: 12px 16px 48px;
  box-sizing: border-box;
}
.onboarding-shell .ptitle,
.onboarding-shell .psub {
  text-align: center;
}
.onboarding-shell .psub {
  margin-bottom: 28px;
}
.onboarding-card {
  padding: 36px 40px 28px;
}
.onboarding-form :deep(.el-form-item) {
  margin-bottom: 28px;
}
.onboarding-form :deep(.el-form-item__label) {
  margin-bottom: 10px;
  line-height: 1.4;
  font-weight: 600;
  color: #303133;
}
.onboarding-form :deep(.submit-row) {
  margin-top: 12px;
  margin-bottom: 0;
}
.onboarding-form :deep(.submit-row .el-form-item__content) {
  justify-content: center;
}
.file-status {
  margin-top: 10px;
  color: #606266;
  font-size: 13px;
  word-break: break-all;
}
.file-hint {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}
.actions {
  margin-top: 24px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}
</style>
