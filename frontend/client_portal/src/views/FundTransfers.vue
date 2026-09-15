<template>
  <div>
    <PageHeader title="Transfers" subtitle="Transfers between nostro accounts" />
    <div class="page-card">
      <div class="toolbar">
        <el-button type="primary" @click="visible = true">Initiate transfer</el-button>
        <el-button @click="load">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="transfer_no" label="Transfer no." min-width="150" />
        <el-table-column prop="from_bank" label="Debit bank" min-width="130" />
        <el-table-column prop="to_bank" label="Credit bank" min-width="130" />
        <el-table-column prop="amount" label="Amount" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="currency" label="Currency" min-width="110" />
        <el-table-column prop="status" label="Status" width="110" />
        <el-table-column label="Creation Time" min-width="160"><template #default="{ row }">{{ datetime(row.created_at) }}</template></el-table-column>
        <el-table-column label="Actions" width="160">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING'" link type="success" @click="execute(row)">Execute</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="Initiate transfer" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Debit account">
          <el-select v-model="form.from_account" filterable style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="`${a.account_no} ${a.bank_name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Credit account">
          <el-select v-model="form.to_account" filterable style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="`${a.account_no} ${a.bank_name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Amount"><el-input v-model="form.amount" /></el-form-item>
        <el-form-item label="Currency"><el-input v-model="form.currency" /></el-form-item>
        <el-form-item label="Narrative"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Submit</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getFundTransfers, createFundTransfer, executeFundTransfer, getNostroAccounts } from '@/api/accounts'
import { unwrapList, datetime, formatMoneyCell } from '@/utils/format'

const rows = ref([])
const accounts = ref([])
const loading = ref(false)
const visible = ref(false)
const form = reactive({ from_account: '', to_account: '', amount: '', currency: 'USD', remark: '' })
async function load() {
  loading.value = true
  try { rows.value = unwrapList(await getFundTransfers({ page_size: 50 })).rows } finally { loading.value = false }
}
async function save() {
  await createFundTransfer(form)
  ElMessage.success('The internal fund-transfer instruction has been submitted.')
  visible.value = false
  load()
}
async function execute(row) {
  await executeFundTransfer(row.transfer_no)
  ElMessage.success('The internal fund transfer has been executed.')
  load()
}
onMounted(async () => {
  accounts.value = unwrapList(await getNostroAccounts({ page_size: 100 })).rows
  load()
})
</script>
