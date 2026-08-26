<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="合作银行" name="coop" />
      <el-tab-pane label="费率模型" name="models" />
      <el-tab-pane label="银行费率配置" name="bankfee" />
    </el-tabs>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" min-width="200">
        <template #default="{ row }">{{ row.name || row.bank_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="bank_code" label="银行编码" min-width="140" v-if="activeTab === 'coop'" />
      <el-table-column prop="currency" label="币种" width="90" v-if="activeTab === 'bankfee'" />
      <el-table-column prop="model_type" label="模型类型" min-width="140" v-if="activeTab === 'models'" />
      <el-table-column prop="rate" label="费率" min-width="120" v-if="activeTab === 'bankfee'" />
      <el-table-column prop="remark" label="备注" min-width="200" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCoopBanks, getFeeModels, getBankFeeConfigs } from '@/api/param'

const activeTab = ref('coop')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const fn = { coop: getCoopBanks, models: getFeeModels, bankfee: getBankFeeConfigs }[activeTab.value]
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
.toolbar { margin-bottom: 16px; }
</style>
