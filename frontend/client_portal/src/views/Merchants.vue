<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="商户号 / 名称" clearable style="width: 220px" @keyup.enter="reload" />
      <el-select v-model="filters.risk_level" placeholder="风险等级" clearable style="width: 140px" @change="reload">
        <el-option label="低" value="LOW" />
        <el-option label="中" value="MEDIUM" />
        <el-option label="高" value="HIGH" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="merchant_no" label="商户号" min-width="150" />
      <el-table-column prop="merchant_name" label="名称" min-width="140" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="risk_level" label="风险" width="90" />
      <el-table-column prop="fee_rate" label="费率%" width="90" />
      <el-table-column prop="fixed_fee" label="固定费" width="90" />
      <el-table-column prop="max_single_amount" label="单笔限额" min-width="110" />
      <el-table-column prop="daily_limit" label="日限额" min-width="110" />
      <el-table-column prop="license_expiry_date" label="执照到期" min-width="120" />
      <el-table-column prop="next_review_date" label="下次复核" min-width="120" />
      <el-table-column label="操作" fixed="right" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="success" @click="openKyc(row)">KYC</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />

    <el-dialog v-model="editVisible" title="客户风险与限额" width="520px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="风险等级">
          <el-select v-model="editForm.risk_level" style="width: 100%">
            <el-option label="低" value="LOW" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="高" value="HIGH" />
            <el-option label="阻断" value="BLOCKED" />
          </el-select>
        </el-form-item>
        <el-form-item label="手续费率%"><el-input v-model="editForm.fee_rate" /></el-form-item>
        <el-form-item label="固定手续费"><el-input v-model="editForm.fixed_fee" /></el-form-item>
        <el-form-item label="单笔限额"><el-input v-model="editForm.max_single_amount" /></el-form-item>
        <el-form-item label="日限额"><el-input v-model="editForm.daily_limit" /></el-form-item>
        <el-form-item label="执照到期"><el-date-picker v-model="editForm.license_expiry_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="kycVisible" title="KYC 审核" width="560px">
      <el-descriptions v-if="kycData" :column="1" border>
        <el-descriptions-item v-for="(v, k) in kycData" :key="k" :label="k">{{ v }}</el-descriptions-item>
      </el-descriptions>
      <el-form :model="kycForm" label-width="110px" style="margin-top: 16px">
        <el-form-item label="风险等级">
          <el-select v-model="kycForm.risk_level" style="width: 100%">
            <el-option label="低" value="LOW" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="高" value="HIGH" />
          </el-select>
        </el-form-item>
        <el-form-item label="单笔限额"><el-input v-model="kycForm.max_single_amount" /></el-form-item>
        <el-form-item label="日限额"><el-input v-model="kycForm.daily_limit" /></el-form-item>
        <el-form-item label="驳回原因"><el-input v-model="kycForm.reason" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button type="danger" @click="doKyc('reject')">驳回</el-button>
        <el-button type="success" @click="doKyc('approve')">通过</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMerchants, updateMerchant, getMerchantKyc, reviewMerchantKyc } from '@/api/merchants'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', risk_level: '' })
const editVisible = ref(false)
const kycVisible = ref(false)
const editForm = reactive({})
const kycForm = reactive({ risk_level: 'MEDIUM', max_single_amount: '', daily_limit: '', reason: '' })
const kycData = ref(null)
let currentNo = ''

async function load() {
  loading.value = true
  try {
    const data = await getMerchants({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      risk_level: filters.risk_level || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.search = ''
  filters.risk_level = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
function openEdit(row) {
  currentNo = row.merchant_no
  Object.assign(editForm, {
    risk_level: row.risk_level,
    fee_rate: row.fee_rate,
    fixed_fee: row.fixed_fee,
    max_single_amount: row.max_single_amount,
    daily_limit: row.daily_limit,
    license_expiry_date: row.license_expiry_date
  })
  editVisible.value = true
}
async function saveEdit() {
  await updateMerchant(currentNo, { ...editForm })
  ElMessage.success('已保存')
  editVisible.value = false
  load()
}
async function openKyc(row) {
  currentNo = row.merchant_no
  try {
    kycData.value = await getMerchantKyc(row.merchant_no)
  } catch {
    kycData.value = { tip: '暂无 KYC 详情' }
  }
  kycVisible.value = true
}
async function doKyc(action) {
  if (action === 'reject' && !kycForm.reason) {
    ElMessage.warning('驳回须填写原因')
    return
  }
  await reviewMerchantKyc(currentNo, { action, ...kycForm })
  ElMessage.success(action === 'approve' ? 'KYC 已通过' : 'KYC 已驳回')
  kycVisible.value = false
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
