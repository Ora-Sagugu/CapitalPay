<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="tab" @tab-change="onTab">
      <el-tab-pane label="代理列表" name="agents" />
      <el-tab-pane label="尽职调查" name="kyc" />
    </el-tabs>

    <div class="toolbar" v-if="tab === 'agents'">
      <el-input v-model="filters.search" placeholder="代理号 / 名称" clearable style="width: 220px" @keyup.enter="loadAgents" />
      <el-button type="primary" @click="loadAgents">查询</el-button>
    </div>

    <el-table v-if="tab === 'agents'" :data="agents" v-loading="loading" border stripe>
      <el-table-column prop="agent_no" label="代理号" min-width="140" />
      <el-table-column prop="agent_name" label="名称" min-width="140" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="kyc_status" label="尽调状态" width="120" />
      <el-table-column prop="commission_rate" label="佣金率" width="100" />
      <el-table-column prop="settlement_bank_name" label="结算银行" min-width="140" />
      <el-table-column prop="settlement_account_no" label="结算账号" min-width="140" />
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button link type="success" @click="activate(row)">启用</el-button>
          <el-button link type="danger" @click="suspend(row)">暂停</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-table v-else :data="kycRows" v-loading="loading" border stripe>
      <el-table-column prop="agent_no" label="代理号" min-width="140" />
      <el-table-column prop="agent_name" label="名称" min-width="140" />
      <el-table-column prop="legal_person" label="法人" width="120" />
      <el-table-column prop="tier" label="等级" width="100" />
      <el-table-column prop="kyc_status" label="状态" width="120" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link @click="submitKyc(row)" v-if="row.kyc_status === 'PENDING'">提交</el-button>
          <el-button link type="success" @click="reviewKyc(row, 'approve')">通过</el-button>
          <el-button link type="danger" @click="reviewKyc(row, 'reject')">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAgents, activateAgent, suspendAgent,
  getAgentKycList, submitAgentKyc, reviewAgentKyc
} from '@/api/agents'

const tab = ref('agents')
const agents = ref([])
const kycRows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '' })

async function loadAgents() {
  loading.value = true
  try {
    const data = await getAgents({ page: page.value, page_size: pageSize.value, search: filters.search || undefined })
    agents.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
async function loadKyc() {
  loading.value = true
  try {
    const data = await getAgentKycList({ page: page.value, page_size: pageSize.value })
    kycRows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
function onTab() {
  page.value = 1
  tab.value === 'agents' ? loadAgents() : loadKyc()
}
function onPage(p) {
  page.value = p
  tab.value === 'agents' ? loadAgents() : loadKyc()
}
async function activate(row) {
  await activateAgent(row.id)
  ElMessage.success('已启用')
  loadAgents()
}
async function suspend(row) {
  await suspendAgent(row.id)
  ElMessage.success('已暂停')
  loadAgents()
}
async function submitKyc(row) {
  await submitAgentKyc(row.id)
  ElMessage.success('已提交')
  loadKyc()
}
async function reviewKyc(row, action) {
  let reason = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt('驳回原因', '尽调驳回', { inputPattern: /.+/ })
    reason = value
  }
  await reviewAgentKyc(row.id, { action, reason })
  ElMessage.success(action === 'approve' ? '尽调通过并启用' : '已驳回')
  loadKyc()
}
onMounted(loadAgents)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
