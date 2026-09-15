<template>
  <div>
    <PageHeader :title="$t('pages.disbursements.title')" :subtitle="$t('pages.disbursements.subtitle')" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" :placeholder="$t('pages.disbursements.search')" clearable style="width: 240px" @keyup.enter="load" />
        <el-select v-model="filters.status" :placeholder="$t('common.status')" clearable style="width: 180px" @change="load">
          <el-option v-for="s in statusOptions" :key="s" :label="$t('pages.disbursements.status_' + s)" :value="s" />
        </el-select>
        <el-button @click="load">{{ $t('common.refresh') }}</el-button>
        <el-button type="primary" @click="openCreate">{{ $t('pages.disbursements.create') }}</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="disbursement_no" :label="$t('pages.disbursements.no')" min-width="150" />
        <el-table-column prop="agent_name" :label="$t('pages.disbursements.agent')" min-width="140" />
        <el-table-column prop="amount" :label="$t('common.amount')" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="110" />
        <el-table-column :label="$t('common.status')" width="150">
          <template #default="{ row }">{{ $t('pages.disbursements.status_' + row.status) }}</template>
        </el-table-column>
        <el-table-column prop="payee_bank_name" :label="$t('pages.disbursements.payeeBank')" min-width="130" />
        <el-table-column prop="payee_account_no" :label="$t('pages.disbursements.payeeAccount')" min-width="140" />
        <el-table-column :label="$t('common.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canApprove && (row.status === 'PENDING_FIRST_APPROVAL' || row.status === 'PENDING_SECOND_APPROVAL')"
              link type="success"
              @click="approve(row)"
            >{{ row.status === 'PENDING_FIRST_APPROVAL' ? $t('pages.disbursements.firstApprove') : $t('pages.disbursements.secondApprove') }}</el-button>
            <el-button
              v-if="canApprove && (row.status === 'PENDING_FIRST_APPROVAL' || row.status === 'PENDING_SECOND_APPROVAL')"
              link type="danger"
              @click="reject(row)"
            >{{ $t('common.reject') }}</el-button>
            <el-button v-if="canApprove && row.status === 'FAILED'" link type="primary" @click="retry(row)">{{ $t('pages.disbursements.retry') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" :title="$t('pages.disbursements.create')" width="520px">
      <el-form :model="form" label-width="120px">
        <el-form-item :label="$t('pages.disbursements.agent')">
          <el-select v-model="form.agent" filterable style="width: 100%">
            <el-option v-for="a in agents" :key="a.id" :label="`${a.agent_no} ${a.agent_name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('common.amount')"><el-input v-model="form.amount" /></el-form-item>
        <el-form-item :label="$t('common.currency')"><el-input v-model="form.currency" /></el-form-item>
        <el-form-item :label="$t('pages.disbursements.payeeBank')"><el-input v-model="form.payee_bank_name" /></el-form-item>
        <el-form-item :label="$t('pages.disbursements.payeeAccount')"><el-input v-model="form.payee_account_no" /></el-form-item>
        <el-form-item :label="$t('pages.disbursements.payeeHolder')"><el-input v-model="form.payee_account_holder" /></el-form-item>
        <el-form-item label="SWIFT"><el-input v-model="form.swift_code" /></el-form-item>
        <el-form-item :label="$t('common.remark')"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="save">{{ $t('common.submit') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/PageHeader.vue'
import { getAgents } from '@/api/agents'
import {
  getDisbursements, createDisbursement, approveDisbursement, rejectDisbursement, executeDisbursement
} from '@/api/disbursements'
import { unwrapList, datetime, formatMoneyCell } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const { t } = useI18n()
const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:disbursements.approve'))
const rows = ref([])
const agents = ref([])
const loading = ref(false)
const visible = ref(false)
const filters = reactive({ search: '', status: '' })
const statusOptions = [
  'PENDING_FIRST_APPROVAL', 'PENDING_SECOND_APPROVAL', 'APPROVED',
  'EXECUTING', 'SUCCESS', 'FAILED', 'REJECTED'
]
const form = reactive({
  agent: '', amount: '', currency: 'CNY', payee_bank_name: '',
  payee_account_no: '', payee_account_holder: '', swift_code: '', remark: ''
})

async function load() {
  loading.value = true
  try {
    const params = { page_size: 50 }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    rows.value = unwrapList(await getDisbursements(params)).rows
  } finally { loading.value = false }
}

function openCreate() { visible.value = true }

async function save() {
  await createDisbursement(form)
  ElMessage.success(t('common.submitted'))
  visible.value = false
  load()
}

async function approve(row) {
  const { value } = await ElMessageBox.prompt(t('pages.disbursements.approverPrompt'), t('pages.disbursements.approveTitle'), {
    inputPlaceholder: t('pages.disbursements.approverPlaceholder'),
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel')
  })
  await approveDisbursement(row.disbursement_no, { approver: value || 'ops' })
  ElMessage.success(t('pages.disbursements.approved'))
  load()
}

async function reject(row) {
  const { value } = await ElMessageBox.prompt(t('pages.disbursements.rejectPrompt'), t('common.reject'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel')
  })
  await rejectDisbursement(row.disbursement_no, { comment: value || '', approver: 'ops' })
  ElMessage.success(t('common.rejected'))
  load()
}

async function retry(row) {
  await executeDisbursement(row.disbursement_no)
  ElMessage.success(t('pages.disbursements.retried'))
  load()
}

onMounted(async () => {
  agents.value = unwrapList(await getAgents({ page_size: 100 })).rows
  load()
})
</script>
