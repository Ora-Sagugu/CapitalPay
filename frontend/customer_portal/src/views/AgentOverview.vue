<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.overviewTitle') }}</h1>
    <p class="psub">{{ $t('agent.overviewSub') }}</p>

    <el-alert
      v-if="auth.onboardingStatus !== 'approved'"
      :title="$t('agent.needOnboarding')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <div class="page-card" v-loading="loading">
      <h2 class="section-heading">{{ $t('agent.profile') }}</h2>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('agent.agentNo')">{{ dash(profile.agent_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.agentName')">{{ dash(profile.agent_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('common.status')">
          <el-tag size="small" :type="statusType(profile.status)">{{ dash(profile.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('agent.legalPerson')">{{ dash(profile.legal_person) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.licenceNo')">{{ dash(profile.business_license_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.contact')">{{ dash(profile.contact_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.phone')">{{ dash(profile.contact_phone) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.kyc')">{{ dash(profile.kyc_status) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.commission')">{{ dash(profile.commission_rate) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.address')" :span="2">{{ dash(profile.registered_address) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.bankName')">{{ dash(profile.settlement_bank_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.accountNo')">{{ dash(profile.settlement_account_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.accountName')">{{ dash(profile.settlement_account_holder) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.swift')">{{ dash(profile.swift_code) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card">
      <h2 class="section-heading">{{ $t('agent.accounts') }}</h2>
      <p class="hint">{{ $t('agent.accountsHint') }}</p>
      <el-table :data="profile.accounts || []">
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="120" />
        <el-table-column :label="$t('accounts.balance')" min-width="160">
          <template #default="{ row }">{{ money(row.balance) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !(profile.accounts || []).length" :description="$t('agent.emptyAccounts')" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/store/auth'
import { getAgentProfile } from '@/api/agent'
import { money } from '@/utils/format'

const auth = useAuthStore()
const loading = ref(false)
const profile = reactive({
  agent_no: '',
  agent_name: '',
  status: '',
  legal_person: '',
  business_license_no: '',
  contact_name: '',
  contact_phone: '',
  kyc_status: '',
  commission_rate: '',
  registered_address: '',
  settlement_bank_name: '',
  settlement_account_no: '',
  settlement_account_holder: '',
  swift_code: '',
  accounts: []
})

function dash(v) {
  return v || '—'
}

function statusType(status) {
  if (status === 'ACTIVE') return 'success'
  if (status === 'SUSPENDED') return 'warning'
  return 'info'
}

onMounted(async () => {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    const data = await getAgentProfile()
    Object.assign(profile, data || {})
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.section-heading { margin: 0 0 12px; font-size: 15px; font-weight: 600; }
.hint { margin: 0 0 12px; color: #8c8c8c; font-size: 13px; }
.page-card + .page-card { margin-top: 16px; }
</style>
