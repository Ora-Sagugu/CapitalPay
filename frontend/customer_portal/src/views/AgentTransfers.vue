<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.transfersTitle') }}</h1>
    <p class="psub">{{ $t('agent.transfersSub') }}</p>
    <div class="page-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">{{ $t('agent.transfersInitiate') }}</el-button>
        <el-button @click="load">{{ $t('common.refresh') }}</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="transfer_no" :label="$t('agent.transferNo')" min-width="150" />
        <el-table-column prop="from_bank" :label="$t('agent.debitBank')" min-width="130" />
        <el-table-column prop="to_bank" :label="$t('agent.creditBank')" min-width="130" />
        <el-table-column prop="amount" :label="$t('common.amount')" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="100" />
        <el-table-column prop="status" :label="$t('common.status')" width="110" />
        <el-table-column :label="$t('accounts.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" width="140">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING'" link type="success" @click="execute(row)">
              {{ $t('agent.transfersExecute') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.emptyTransfers')" />
    </div>

    <el-dialog v-model="visible" :title="$t('agent.transfersInitiate')" width="480px">
      <el-form :model="form" label-width="110px">
        <el-form-item :label="$t('agent.debitAccount')">
          <el-select v-model="form.from_account" filterable style="width: 100%" @change="syncCurrency">
            <el-option
              v-for="a in accounts"
              :key="a.id"
              :label="accountLabel(a)"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('agent.creditAccount')">
          <el-select v-model="form.to_account" filterable style="width: 100%">
            <el-option
              v-for="a in accounts"
              :key="a.id"
              :label="accountLabel(a)"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('common.amount')">
          <el-input v-model="form.amount" />
        </el-form-item>
        <el-form-item :label="$t('common.currency')">
          <el-input v-model="form.currency" disabled />
        </el-form-item>
        <el-form-item :label="$t('agent.narrative')">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ $t('common.submit') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import {
  getAgentFundTransfers,
  createAgentFundTransfer,
  executeAgentFundTransfer,
  getAgentFundTransferAccounts
} from '@/api/agent'
import { datetime, formatMoneyCell } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const accounts = ref([])
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const form = reactive({
  from_account: '',
  to_account: '',
  amount: '',
  currency: 'USD',
  remark: ''
})

function accountLabel(a) {
  const parts = [a.account_no, a.bank_name || a.account_type, a.currency].filter(Boolean)
  return parts.join(' · ')
}

function syncCurrency() {
  const selected = accounts.value.find((a) => a.id === form.from_account)
  if (selected?.currency) form.currency = selected.currency
}

function openCreate() {
  form.from_account = ''
  form.to_account = ''
  form.amount = ''
  form.currency = accounts.value[0]?.currency || 'USD'
  form.remark = ''
  visible.value = true
}

async function loadAccounts() {
  const data = await getAgentFundTransferAccounts()
  accounts.value = data.items || []
}

async function load() {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    const data = await getAgentFundTransfers({ page_size: 50 })
    rows.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.from_account || !form.to_account || !form.amount) {
    ElMessage.warning(t('agent.transfersRequired'))
    return
  }
  saving.value = true
  try {
    await createAgentFundTransfer({
      from_account: form.from_account,
      to_account: form.to_account,
      amount: form.amount,
      remark: form.remark
    })
    ElMessage.success(t('agent.transfersCreated'))
    visible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function execute(row) {
  await executeAgentFundTransfer(row.transfer_no)
  ElMessage.success(t('agent.transfersExecuted'))
  await load()
}

onMounted(async () => {
  if (auth.onboardingStatus !== 'approved') return
  try {
    await loadAccounts()
  } catch {
    accounts.value = []
  }
  await load()
})
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
