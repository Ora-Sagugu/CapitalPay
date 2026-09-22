<template>
  <div>
    <h1 class="ptitle">{{ $t('profile.title') }}</h1>
    <p class="psub">{{ $t('profile.subtitle') }}</p>

    <div class="page-card" v-loading="loading" data-testid="profile-basic">
      <h2 class="section-heading">{{ $t('profile.basic') }}</h2>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('onboarding.legalName')">
          {{ dash(basic.legal_name || account.real_name) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.idType')">
          {{ idTypeLabel(basic.id_type) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.idNumber')">
          {{ dash(basic.id_number) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.nationality')">
          {{ dash(basic.nationality) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.phone')">
          {{ dash(basic.contact_phone || account.phone) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.email')">
          {{ dash(account.email) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.address')" :span="2">
          {{ dash(basic.address) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.licenceExpiry')">
          {{ dash(basic.license_expiry_date) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.onboardingStatus')">
          <el-tag size="small" :type="statusType(account.onboarding_status)">
            {{ dash(account.onboarding_status) }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card" v-loading="loading" data-testid="profile-merchant">
      <h2 class="section-heading">{{ $t('profile.merchant') }}</h2>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('profile.merchantNo')">
          {{ dash(account.merchant_no) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.merchantName')">
          {{ dash(account.merchant_name) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.merchantStatus')">
          <el-tag size="small" :type="statusType(account.merchant_status)">
            {{ dash(account.merchant_status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.kycStatus')">
          {{ dash(account.merchant_kyc_status) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.agentName')">
          {{ dash(account.agent_name) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('profile.agentCode')">
          {{ dash(account.agent_no) }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { getProfile } from '@/api/auth'
import { getOnboardingStatus } from '@/api/onboarding'

const { t } = useI18n()
const auth = useAuthStore()
const loading = ref(false)

const account = reactive({
  real_name: '',
  phone: '',
  email: '',
  onboarding_status: '',
  merchant_no: '',
  merchant_name: '',
  merchant_status: '',
  merchant_kyc_status: '',
  agent_name: '',
  agent_no: ''
})

const basic = reactive({
  legal_name: '',
  id_type: '',
  id_number: '',
  contact_phone: '',
  nationality: '',
  address: '',
  license_expiry_date: ''
})

function dash(v) {
  return v || '—'
}

function idTypeLabel(code) {
  if (!code) return '—'
  const key = `onboarding.idTypes.${code}`
  const label = t(key)
  return label === key ? code : label
}

function statusType(status) {
  if (status === 'approved' || status === 'ACTIVE' || status === 'APPROVED') return 'success'
  if (status === 'pending' || status === 'PENDING' || status === 'under_review') return 'warning'
  if (status === 'rejected' || status === 'REJECTED' || status === 'SUSPENDED') return 'danger'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const [profile, onboarding] = await Promise.all([
      getProfile(),
      getOnboardingStatus()
    ])
    Object.assign(account, {
      real_name: profile.real_name || '',
      phone: profile.phone || '',
      email: profile.email || '',
      onboarding_status: profile.onboarding_status || '',
      merchant_no: profile.merchant_no || '',
      merchant_name: profile.merchant_name || '',
      merchant_status: profile.merchant_status || '',
      merchant_kyc_status: profile.merchant_kyc_status || '',
      agent_name: profile.agent_name || '',
      agent_no: profile.agent_no || ''
    })
    auth.mergeUser(profile)
    const b = onboarding?.data?.basic || {}
    Object.assign(basic, {
      legal_name: b.legal_name || '',
      id_type: b.id_type || '',
      id_number: b.id_number || '',
      contact_phone: b.contact_phone || '',
      nationality: b.nationality || '',
      address: b.address || '',
      license_expiry_date: b.license_expiry_date || ''
    })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.page-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.section-heading { margin: 0 0 12px; font-size: 16px; font-weight: 600; }
</style>
