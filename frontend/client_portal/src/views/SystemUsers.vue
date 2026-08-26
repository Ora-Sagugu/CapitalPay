<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="账号 / 姓名" clearable style="width: 220px" @keyup.enter="reload" />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="username" label="账号" min-width="140" />
      <el-table-column prop="real_name" label="姓名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="roles" label="角色" min-width="160">
        <template #default="{ row }">{{ (row.roles || []).join(' / ') }}</template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="resetPwd(row)">重置密码</el-button>
          <el-button link type="warning" @click="toggleStatus(row)">{{ row.is_active ? '禁用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-tabs v-model="activeTab" class="toolbar" @tab-change="onTab">
      <el-tab-pane label="角色" name="roles" />
      <el-tab-pane label="权限" name="permissions" />
      <el-tab-pane label="操作日志" name="logs" />
    </el-tabs>

    <el-table :data="subRows" v-loading="subLoading" border stripe>
      <el-table-column prop="code" label="编码" min-width="160" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="description" label="描述" min-width="220" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getUsers, resetUserPassword, toggleUserStatus, getRoles, getPermissions, getOperationLogs } from '@/api/rbac'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '' })

const activeTab = ref('roles')
const subRows = ref([])
const subLoading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getUsers({ page: page.value, page_size: pageSize.value, search: filters.search || undefined })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
async function loadSub() {
  subLoading.value = true
  try {
    const fn = { roles: getRoles, permissions: getPermissions, logs: getOperationLogs }[activeTab.value]
    const data = await fn({ page: 1, page_size: 20 })
    subRows.value = data.results || []
  } finally {
    subLoading.value = false
  }
}
async function resetPwd(row) {
  await resetUserPassword(row.id)
  ElMessage.success('密码已重置')
}
async function toggleStatus(row) {
  await toggleUserStatus(row.id, { is_active: !row.is_active })
  ElMessage.success('状态已更新')
  load()
}
function onTab() {
  loadSub()
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.search = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(() => {
  load()
  loadSub()
})
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
