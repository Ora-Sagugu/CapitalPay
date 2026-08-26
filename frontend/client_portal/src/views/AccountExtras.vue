<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="Nostro 往来账户" name="nostro" />
      <el-tab-pane label="充值请求" name="deposits" />
      <el-tab-pane label="用户支付详情" name="payments" />
    </el-tabs>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="account_no" label="账户" min-width="180" />
      <el-table-column prop="bank_name" label="银行" min-width="140" v-if="activeTab === 'nostro'" />
      <el-table-column prop="currency" label="币种" width="90" v-if="activeTab === 'nostro' || activeTab === 'deposits'" />
      <el-table-column prop="balance" label="余额" min-width="120" v-if="activeTab === 'nostro'" />
      <el-table-column prop="amount" label="金额" min-width="120" v-if="activeTab === 'deposits' || activeTab === 'payments'" />
      <el-table-column prop="status" label="状态" min-width="120" />
      <el-table-column prop="merchant_name" label="关联商户" min-width="160" v-if="activeTab === 'deposits'" />
      <el-table-column prop="detail_no" label="支付单号" min-width="180" v-if="activeTab === 'payments'" />
      <el-table-column prop="created_at" label="创建时间" min-width="160" v-if="activeTab === 'deposits'" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getNostroAccounts, getDeposits, getUserPaymentDetails } from '@/api/accounts'

const activeTab = ref('nostro')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const fn = { nostro: getNostroAccounts, deposits: getDeposits, payments: getUserPaymentDetails }[activeTab.value]
    const data = await fn({ page: page.value, page_size: pageSize.value })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
function onTab() {
  page.value = 1
  load()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-top: 16px; }
</style>
