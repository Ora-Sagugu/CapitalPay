<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="终端用户 Onboarding" name="onboarding" />
      <el-tab-pane label="终端用户账户" name="accounts" />
      <el-tab-pane label="终端用户支付" name="payments" />
    </el-tabs>

    <div class="toolbar" v-if="activeTab === 'onboarding'">
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已拒绝" value="rejected" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" min-width="160" v-if="activeTab === 'onboarding'">
        <template #default="{ row }">{{ row.name || row.contact_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="account_no" label="账户" min-width="160" v-if="activeTab === 'accounts'" />
      <el-table-column prop="email" label="邮箱" min-width="180" v-if="activeTab === 'onboarding'" />
      <el-table-column prop="phone" label="手机" min-width="140" v-if="activeTab === 'accounts' || activeTab === 'onboarding'" />
      <el-table-column prop="status" label="状态" min-width="120" v-if="activeTab === 'onboarding'" />
      <el-table-column prop="order_no" label="订单号" min-width="180" v-if="activeTab === 'payments'" />
      <el-table-column prop="amount" label="金额" min-width="120" v-if="activeTab === 'payments'" />
      <el-table-column prop="currency" label="币种" width="90" v-if="activeTab === 'payments'" />
      <el-table-column label="操作" width="200" fixed="right" v-if="activeTab === 'onboarding'">
        <template #default="{ row }">
          <el-button link type="primary" @click="review(row)" :disabled="row.status !== 'pending' && row.onboarding_status !== 'pending'">审核</el-button>
          <el-button link type="warning" @click="toggle(row)">启停</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOnboardingList, reviewOnboarding, toggleOnboardingStatus, getUserAccounts, getUserPayments } from '@/api/userPortal'

const activeTab = ref('onboarding')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ status: '' })

async function load() {
  loading.value = true
  try {
    const fn = { onboarding: getOnboardingList, accounts: getUserAccounts, payments: getUserPayments }[activeTab.value]
    const data = await fn({ page: page.value, page_size: pageSize.value, status: filters.status || undefined })
    rows.value = data.results || []
    total.value = data.count || data.total || 0
  } finally {
    loading.value = false
  }
}
function onTab() {
  page.value = 1
  load()
}
async function review(row) {
  await reviewOnboarding(row.id, { action: 'approve' })
  ElMessage.success('审核通过')
  load()
}
async function toggle(row) {
  await toggleOnboardingStatus(row.id)
  ElMessage.success('状态已更新')
  load()
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.status = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
