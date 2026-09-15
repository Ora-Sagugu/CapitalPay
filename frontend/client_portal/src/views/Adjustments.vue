<template>
  <div>
    <PageHeader title="Adjustments" subtitle="Manual adjustments and discrepancy items" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.order_no" placeholder="Order reference" clearable style="width: 180px" />
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 140px" @change="load">
          <el-option label="Pending review" value="pending" />
          <el-option label="Approved" value="approved" />
          <el-option label="Rejected" value="rejected" />
        </el-select>
        <el-button @click="load">Search</el-button>
        <el-button type="primary" @click="visible = true">Create ledger adjustment</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="application_no" label="Application no." min-width="150" />
        <el-table-column prop="order_no" label="Order reference" min-width="150" />
        <el-table-column prop="diff_type" label="Discrepancy type" min-width="120" />
        <el-table-column prop="amount" label="Amount" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column label="Status" width="110">
          <template #default="{ row }"><StatusPill kind="onboarding" :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Actions" width="160">
          <template #default="{ row }">
            <el-button v-if="canApprove" link type="success" @click="approve(row)">Approve</el-button>
            <el-button v-if="canApprove" link type="danger" @click="reject(row)">Reject</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="Create ledger adjustment" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Order No."><el-input v-model="form.order_no" /></el-form-item>
        <el-form-item label="Discrepancy type">
          <el-select v-model="form.diff_type" style="width: 100%">
            <el-option label="Amount discrepancy" value="amount" />
            <el-option label="Item-count discrepancy" value="count" />
            <el-option label="Status discrepancy" value="status" />
            <el-option label="Duplicate transaction" value="duplicate" />
            <el-option label="Missing transaction" value="missing" />
          </el-select>
        </el-form-item>
        <el-form-item label="Amount"><el-input v-model="form.amount" /></el-form-item>
        <el-form-item label="Reason"><el-input v-model="form.reason" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Submit</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getAdjustments, createAdjustment, approveAdjustment, rejectAdjustment } from '@/api/adjustment'
import { unwrapList, formatMoneyCell } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:adjustments.approve'))

const rows = ref([])
const loading = ref(false)
const visible = ref(false)
const filters = reactive({ order_no: '', status: '' })
const form = reactive({ order_no: '', diff_type: 'amount', amount: '', reason: '' })
async function load() {
  loading.value = true
  try { rows.value = unwrapList(await getAdjustments(filters)).rows } finally { loading.value = false }
}
async function save() {
  await createAdjustment({
    ...form,
    applicant: 'admin',
    adjustment_amount: form.amount
  })
  ElMessage.success('The ledger-adjustment application has been submitted.')
  visible.value = false
  load()
}
async function approve(row) { await approveAdjustment(row.id); load() }
async function reject(row) {
  const { value } = await ElMessageBox.prompt('Enter the grounds for rejection', 'Reject', { inputPattern: /.+/, inputErrorMessage: 'A rejection reason is required.' })
  await rejectAdjustment(row.id, { comment: value })
  load()
}
onMounted(load)
</script>
