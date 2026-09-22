<template>
  <div>
    <h1 class="ptitle">{{ $t('customers.title') }}</h1>
    <p class="psub">{{ $t('customers.subtitle') }}</p>
    <div class="page-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">{{ $t('customers.create') }}</el-button>
        <el-button @click="reload">{{ $t('common.refresh') }}</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="customer_no" :label="$t('customers.customerNo')" min-width="140" />
        <el-table-column prop="legal_name" :label="$t('customers.customerName')" min-width="180" />
        <el-table-column :label="$t('common.status')" width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.kyc_status)" size="small">{{ statusLabel(row.kyc_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact_email" :label="$t('agent.kycEmail')" min-width="180" />
        <el-table-column :label="$t('common.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">{{ $t('common.edit') }}</el-button>
            <el-button
              link
              type="primary"
              :disabled="!row.remittance_eligibility?.eligible"
              :title="$t('customers.remitHint')"
              data-testid="remit-btn"
              @click="goRemit(row)"
            >
              {{ $t('customers.remitAction') }}
            </el-button>
            <el-button
              link
              type="danger"
              data-testid="delete-btn"
              @click="remove(row)"
            >
              {{ $t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('customers.empty')" />
    </div>

    <el-dialog v-model="visible" :title="form.id ? $t('customers.edit') : $t('customers.create')" width="560px">
      <el-form :model="form" label-width="140px">
        <el-form-item :label="$t('onboarding.legalName')" required>
          <el-input v-model="form.legal_name" />
        </el-form-item>
        <el-form-item :label="$t('agent.kycEmail')">
          <el-input v-model="form.contact_email" />
        </el-form-item>
        <el-form-item :label="$t('onboarding.idType')">
          <el-select v-model="form.id_type" clearable style="width: 100%">
            <el-option
              v-for="(label, code) in idTypeOptions"
              :key="code"
              :label="label"
              :value="code"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('onboarding.idNumber')">
          <el-input v-model="form.id_number" />
        </el-form-item>
        <el-form-item :label="$t('customers.country')">
          <el-input v-model="form.nationality" />
        </el-form-item>
        <el-form-item :label="$t('onboarding.address')">
          <el-input v-model="form.address" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import {
  createCustomer,
  deleteCustomer,
  getCustomers,
  updateCustomer
} from '@/api/payments'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const rows = ref([])
const form = reactive(emptyForm())

const idTypeOptions = computed(() => ({
  id_card: t('onboarding.idTypes.id_card'),
  passport: t('onboarding.idTypes.passport'),
  business_license: t('onboarding.idTypes.business_license'),
  other: t('onboarding.idTypes.other')
}))

function emptyForm() {
  return {
    id: '',
    legal_name: '',
    contact_email: '',
    id_type: '',
    id_number: '',
    nationality: '',
    address: ''
  }
}

function statusLabel(code) {
  if (code === 'approved') return t('agent.kycStatusApproved')
  if (code === 'rejected') return t('agent.kycStatusRejected')
  if (code === 'submitted') return t('agent.kycStatusPending')
  return t('agent.kycStatusDraft')
}

function statusType(code) {
  if (code === 'approved') return 'success'
  if (code === 'rejected') return 'danger'
  if (code === 'submitted') return 'warning'
  return 'info'
}

function goRemit(row) {
  router.push({ name: 'remittance', query: { customer_id: row.id } })
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      t('customers.deleteConfirm', { name: row.legal_name || row.customer_name || row.customer_no }),
      t('common.hint'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel')
      }
    )
  } catch {
    return
  }
  await deleteCustomer(row.id)
  ElMessage.success(t('customers.deleted'))
  await reload()
}

function openCreate() {
  Object.assign(form, emptyForm())
  visible.value = true
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    id: row.id,
    legal_name: row.legal_name || row.customer_name || '',
    contact_email: row.contact_email || '',
    id_type: row.id_type || '',
    id_number: row.id_number || '',
    nationality: row.nationality || '',
    address: row.address || ''
  })
  visible.value = true
}

async function save() {
  if (!(form.legal_name || '').trim()) {
    ElMessage.warning(t('customers.nameRequired'))
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (form.id) await updateCustomer(form.id, payload)
    else await createCustomer(payload)
    ElMessage.success(t('customers.saved'))
    visible.value = false
    await reload()
  } finally {
    saving.value = false
  }
}

async function reload() {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    const data = await getCustomers()
    rows.value = data.items || data.results || []
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
