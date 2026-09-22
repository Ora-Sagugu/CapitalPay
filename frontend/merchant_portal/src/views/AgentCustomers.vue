<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.customersTitle') }}</h1>
    <p class="psub">{{ $t('agent.customersSub') }}</p>

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
          v-model="search"
          :placeholder="$t('agent.customersSearch')"
          clearable
          style="width: 300px"
          @clear="load"
          @keyup.enter="load"
        />
        <el-button @click="load">{{ $t('common.refresh') }}</el-button>
        <span class="kpi">{{ $t('agent.customersTotal') }} {{ filteredRows.length }}</span>
      </div>
      <el-table :data="filteredRows" v-loading="loading">
        <el-table-column prop="customer_no" :label="$t('customers.customerNo')" min-width="140" />
        <el-table-column prop="legal_name" :label="$t('customers.customerName')" min-width="160" />
        <el-table-column prop="merchant_no" :label="$t('agent.merchantsNo')" min-width="140" />
        <el-table-column prop="merchant_name" :label="$t('agent.merchantsName')" min-width="160" />
        <el-table-column prop="contact_email" :label="$t('agent.kycEmail')" min-width="180" />
        <el-table-column :label="$t('onboarding.idType')" min-width="120">
          <template #default="{ row }">{{ idTypeLabel(row.id_type) }}</template>
        </el-table-column>
        <el-table-column prop="id_number" :label="$t('onboarding.idNumber')" min-width="140" />
        <el-table-column prop="nationality" :label="$t('customers.country')" min-width="110" />
        <el-table-column :label="$t('common.status')" min-width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.kyc_status)" size="small">{{ statusLabel(row.kyc_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ $t('common.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filteredRows.length" :description="$t('agent.customersEmpty')" />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="480px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item :label="$t('customers.customerNo')">{{ dash(detail.customer_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('customers.customerName')">{{ dash(detail.legal_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.merchantsNo')">{{ dash(detail.merchant_no) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.merchantsName')">{{ dash(detail.merchant_name) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('agent.kycEmail')">{{ dash(detail.contact_email) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.idType')">{{ idTypeLabel(detail.id_type) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.idNumber')">{{ dash(detail.id_number) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('customers.country')">{{ dash(detail.nationality) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('onboarding.address')">{{ dash(detail.address) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('common.status')">{{ statusLabel(detail.kyc_status) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { getAgentCustomers } from '@/api/agent'
import { extractErrorMessage } from '@/api/error'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const loading = ref(false)
const search = ref('')
const detailVisible = ref(false)
const detail = ref(null)

const detailTitle = computed(() => {
  if (!detail.value) return t('agent.customersTitle')
  return detail.value.legal_name || detail.value.customer_no || t('agent.customersTitle')
})

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((row) => {
    const hay = [
      row.customer_no,
      row.legal_name,
      row.merchant_no,
      row.merchant_name,
      row.contact_email,
      row.id_number,
      row.nationality
    ].join(' ').toLowerCase()
    return hay.includes(q)
  })
})

const ID_TYPE_LABELS = {
  id_card: 'ID No.',
  passport: 'Passport',
  business_license: 'Business Licence',
  other: 'Other'
}

function dash(value) {
  return value || '—'
}

function idTypeLabel(code) {
  if (!code) return '—'
  return ID_TYPE_LABELS[code] || t(`onboarding.idTypes.${code}`, code)
}

function statusLabel(code) {
  if (code === 'approved') return t('agent.kycStatusApproved')
  if (code === 'rejected') return t('agent.kycStatusRejected')
  if (code === 'submitted') return t('agent.kycStatusPending')
  if (code === 'draft') return t('agent.kycStatusDraft')
  return code || '—'
}

function statusType(code) {
  const value = String(code || '').toLowerCase()
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'danger'
  if (value === 'submitted') return 'warning'
  return 'info'
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

async function load() {
  if (auth.onboardingStatus !== 'approved') {
    rows.value = []
    return
  }
  loading.value = true
  try {
    const data = await getAgentCustomers()
    rows.value = data.items || data.results || []
  } catch (err) {
    rows.value = []
    ElMessage.error(extractErrorMessage(err?.response?.data, t('agent.customersEmpty')))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.kpi { color: #8c8c8c; font-size: 13px; }
</style>
