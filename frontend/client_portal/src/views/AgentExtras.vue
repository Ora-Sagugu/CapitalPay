<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="代理-商户绑定" name="merchants" />
      <el-tab-pane label="代理佣金" name="commissions" />
      <el-tab-pane label="代理费率配置" name="fee" />
    </el-tabs>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="agent_name" label="代理" min-width="160" v-if="activeTab === 'merchants' || activeTab === 'commissions' || activeTab === 'fee'" />
      <el-table-column prop="merchant_name" label="商户" min-width="160" v-if="activeTab === 'merchants'" />
      <el-table-column prop="order_no" label="关联订单" min-width="180" v-if="activeTab === 'commissions'" />
      <el-table-column prop="commission_amount" label="佣金金额" min-width="140" v-if="activeTab === 'commissions'" />
      <el-table-column prop="currency" label="币种" width="90" v-if="activeTab === 'commissions' || activeTab === 'fee'" />
      <el-table-column prop="fee_type" label="费率类型" min-width="140" v-if="activeTab === 'fee'" />
      <el-table-column prop="fee_rate" label="费率" min-width="120" v-if="activeTab === 'fee'" />
      <el-table-column prop="status" label="状态" min-width="120" v-if="activeTab === 'merchants'" />
      <el-table-column prop="period" label="结算周期" min-width="140" v-if="activeTab === 'commissions'" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAgentMerchants, getAgentCommissions, getAgentFeeConfigs } from '@/api/agents'

const activeTab = ref('merchants')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const fn = { merchants: getAgentMerchants, commissions: getAgentCommissions, fee: getAgentFeeConfigs }[activeTab.value]
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
