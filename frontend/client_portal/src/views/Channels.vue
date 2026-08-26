<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="银行通道" name="channels" />
      <el-tab-pane label="路由规则" name="rules" />
      <el-tab-pane label="路由日志" name="routinglogs" />
    </el-tabs>

    <div class="toolbar" v-if="activeTab === 'rules'">
      <el-button type="primary" @click="addRule">新增规则</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" min-width="180" v-if="activeTab === 'channels'">
        <template #default="{ row }">{{ row.name || row.channel_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="channel_code" label="通道编码" min-width="140" v-if="activeTab === 'channels'" />
      <el-table-column prop="bank_name" label="银行" min-width="140" v-if="activeTab === 'channels'" />
      <el-table-column prop="status" label="启用" width="90" v-if="activeTab === 'channels'">
        <template #default="{ row }">
          <el-switch :model-value="row.status === 'active'" @change="() => toggleStatus(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="rule_name" label="规则名" min-width="180" v-if="activeTab === 'rules'" />
      <el-table-column prop="priority" label="优先级" width="100" v-if="activeTab === 'rules'" />
      <el-table-column prop="order_no" label="关联订单" min-width="180" v-if="activeTab === 'routinglogs'" />
      <el-table-column prop="channel_code" label="命中通道" min-width="140" v-if="activeTab === 'routinglogs'" />
      <el-table-column prop="result" label="结果" min-width="120" v-if="activeTab === 'routinglogs'" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getChannels, toggleChannelStatus, getRoutingRules, createRoutingRule, getRoutingLogs } from '@/api/routing'

const activeTab = ref('channels')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const fn = { channels: getChannels, rules: getRoutingRules, routinglogs: getRoutingLogs }[activeTab.value]
    const data = await fn({ page: page.value, page_size: pageSize.value })
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
async function toggleStatus(row) {
  await toggleChannelStatus(row.id)
  ElMessage.success('通道状态已更新')
  load()
}
async function addRule() {
  await createRoutingRule({ rule_name: '新规则', priority: 10 })
  ElMessage.success('规则已新增')
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
