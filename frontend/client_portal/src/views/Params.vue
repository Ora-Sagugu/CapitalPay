<template>
  <div>
    <PageHeader title="Parameters" subtitle="Banks, fee models and channel charges">
      <el-button type="primary" @click="openCreate">+ Create</el-button>
    </PageHeader>
    <el-tabs v-model="tab" @tab-change="onTab">
      <el-tab-pane label="Banks" name="coop" />
      <el-tab-pane label="Fee models" name="models" />
      <el-tab-pane label="Bank charges" name="bankfee" />
    </el-tabs>
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="search" placeholder="Search" clearable style="width: 220px" @keyup.enter="load" />
        <el-button @click="load">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe>
        <template v-if="tab === 'coop'">
          <el-table-column prop="bank_code" label="Bank Code" min-width="120" />
          <el-table-column prop="bank_name" label="Bank name" min-width="150" />
          <el-table-column prop="swift_code" label="SWIFT" min-width="110" />
          <el-table-column prop="country" label="Country" width="90" />
          <el-table-column prop="status" label="Status" width="110" />
        </template>
        <template v-else-if="tab === 'models'">
          <el-table-column prop="model_code" label="Model code" min-width="120" />
          <el-table-column prop="model_name" label="Model name" min-width="140" />
          <el-table-column prop="fee_type" label="Type" width="110" />
          <el-table-column prop="base_rate" label="Base rate" width="110" />
          <el-table-column prop="min_fee" label="Minimum" width="90" :formatter="formatMoneyCell" />
          <el-table-column prop="max_fee" label="Maximum" width="90" :formatter="formatMoneyCell" />
          <el-table-column prop="status" label="Status" width="90" />
        </template>
        <template v-else>
          <el-table-column prop="bank_name" label="Bank" min-width="140" />
          <el-table-column prop="fee_model_name" label="Fee model" min-width="140" />
          <el-table-column prop="channel_type" label="Channel type" width="110" />
          <el-table-column prop="override_rate" label="Override rate" width="110" />
          <el-table-column prop="status" label="Status" width="90" />
        </template>
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
            <el-button link type="danger" @click="remove(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>

    <el-dialog v-model="visible" :title="form.id ? 'Edit' : 'Create'" width="560px">
      <el-form :model="form" label-width="120px">
        <template v-if="tab === 'coop'">
          <el-form-item label="Bank Code"><el-input v-model="form.bank_code" /></el-form-item>
          <el-form-item label="Bank name"><el-input v-model="form.bank_name" /></el-form-item>
          <el-form-item label="SWIFT"><el-input v-model="form.swift_code" /></el-form-item>
          <el-form-item label="Country"><el-input v-model="form.country" /></el-form-item>
          <el-form-item label="Status">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="Active" value="active" />
              <el-option label="Suspended" value="suspended" />
              <el-option label="Terminated" value="terminated" />
            </el-select>
          </el-form-item>
        </template>
        <template v-else-if="tab === 'models'">
          <el-form-item label="Model code"><el-input v-model="form.model_code" :disabled="!!form.id" /></el-form-item>
          <el-form-item label="Model name"><el-input v-model="form.model_name" /></el-form-item>
          <el-form-item label="Fee type">
            <el-select v-model="form.fee_type" style="width: 100%">
              <el-option label="Flat rate" value="fixed" />
              <el-option label="Tiered rate" value="tiered" />
              <el-option label="Mixed rate" value="mixed" />
            </el-select>
          </el-form-item>
          <el-form-item label="Base rate"><el-input v-model="form.base_rate" /></el-form-item>
          <el-form-item label="Minimum fee"><el-input v-model="form.min_fee" /></el-form-item>
          <el-form-item label="Maximum fee"><el-input v-model="form.max_fee" /></el-form-item>
          <el-form-item label="Status">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="Active" value="active" />
              <el-option label="Inactive" value="inactive" />
            </el-select>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="Bank">
            <el-select v-model="form.bank" style="width: 100%">
              <el-option v-for="b in banks" :key="b.id" :label="b.bank_name" :value="b.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="Fee model">
            <el-select v-model="form.fee_model" style="width: 100%">
              <el-option v-for="m in models" :key="m.id" :label="m.model_name" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="Channel type">
            <el-select v-model="form.channel_type" style="width: 100%">
              <el-option label="Online banking" value="online" />
              <el-option label="Wire transfer" value="wire" />
              <el-option label="ACH" value="ach" />
              <el-option label="Real-time payment" value="realtime" />
            </el-select>
          </el-form-item>
          <el-form-item label="Override rate"><el-input v-model="form.override_rate" /></el-form-item>
          <el-form-item label="Status">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="Active" value="active" />
              <el-option label="Inactive" value="inactive" />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import {
  getCoopBanks, createCoopBank, updateCoopBank, deleteCoopBank,
  getFeeModels, createFeeModel, updateFeeModel, deleteFeeModel,
  getBankFeeConfigs, createBankFeeConfig, updateBankFeeConfig, deleteBankFeeConfig
} from '@/api/param'
import { unwrapList, formatMoneyCell } from '@/utils/format'

const tab = ref('coop')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const search = ref('')
const visible = ref(false)
const form = reactive({})
const banks = ref([])
const models = ref([])

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, search: search.value || undefined }
    let data
    if (tab.value === 'coop') data = await getCoopBanks(params)
    else if (tab.value === 'models') data = await getFeeModels(params)
    else data = await getBankFeeConfigs(params)
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally { loading.value = false }
}
function onTab() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function blank() {
  if (tab.value === 'coop') return { bank_code: '', bank_name: '', swift_code: '', country: 'China', status: 'active' }
  if (tab.value === 'models') return { model_code: '', model_name: '', fee_type: 'fixed', base_rate: '0.003', min_fee: '1', max_fee: '500', status: 'active' }
  return { bank: '', fee_model: '', channel_type: 'wire', override_rate: '', status: 'active' }
}
async function openCreate() {
  banks.value = unwrapList(await getCoopBanks({ page_size: 100 })).rows
  models.value = unwrapList(await getFeeModels({ page_size: 100 })).rows
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, blank())
  visible.value = true
}
async function openEdit(row) {
  banks.value = unwrapList(await getCoopBanks({ page_size: 100 })).rows
  models.value = unwrapList(await getFeeModels({ page_size: 100 })).rows
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, { ...row, bank: row.bank || row.bank_id, fee_model: row.fee_model || row.fee_model_id })
  visible.value = true
}
async function save() {
  const payload = { ...form }
  const id = payload.id
  delete payload.id
  delete payload.created_at
  delete payload.updated_at
  delete payload.is_deleted
  if (tab.value !== 'coop') delete payload.bank_name
  delete payload.fee_model_name
  if (tab.value === 'coop') {
    if (id) await updateCoopBank(id, payload)
    else await createCoopBank(payload)
  } else if (tab.value === 'models') {
    if (id) await updateFeeModel(id, payload)
    else await createFeeModel(payload)
  } else {
    if (id) await updateBankFeeConfig(id, payload)
    else await createBankFeeConfig(payload)
  }
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}
async function remove(row) {
  await ElMessageBox.confirm('Delete this record?', 'Confirmation', { type: 'warning' })
  if (tab.value === 'coop') await deleteCoopBank(row.id)
  else if (tab.value === 'models') await deleteFeeModel(row.id)
  else await deleteBankFeeConfig(row.id)
  ElMessage.success('The record has been deleted.')
  load()
}
onMounted(load)
</script>
<style scoped>
.toolbar { margin: 12px 0; display: flex; gap: 8px; }
</style>
