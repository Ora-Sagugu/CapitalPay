<template>
  <div>
    <PageHeader title="Users" subtitle="Operations and end-user accounts" />
    <div class="page-card">
      <el-tabs v-model="tab" @tab-change="reload">
        <el-tab-pane label="Operations" name="ops" />
        <el-tab-pane label="End users" name="end" />
      </el-tabs>
      <el-tabs v-if="tab === 'ops'" v-model="opsTab" type="card" @tab-change="reload">
        <el-tab-pane label="Account list" name="opsUsers" />
        <el-tab-pane label="Audit log" name="logs" />
      </el-tabs>
      <el-tabs v-else v-model="endTab" type="card" @tab-change="reload">
        <el-tab-pane label="User list" name="endUsers" />
        <el-tab-pane label="Bank accounts" name="accounts" />
        <el-tab-pane label="Payment records" name="payments" />
      </el-tabs>
      <div class="toolbar">
        <el-input
          v-if="searchable"
          v-model="filters.search"
          :placeholder="searchPlaceholder"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <el-button @click="reload">Refresh</el-button>
        <el-button v-if="activeView === 'opsUsers'" type="primary" @click="openCreate">+ New user</el-button>
      </div>
      <el-table v-if="activeView === 'opsUsers'" :data="rows" v-loading="loading">
        <el-table-column prop="username" label="Username" min-width="120" />
        <el-table-column prop="real_name" label="Legal name" min-width="120" />
        <el-table-column prop="email" label="Email" min-width="180" />
        <el-table-column prop="phone" label="Mobile number" min-width="130" />
        <el-table-column label="Role" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles || []" :key="r" size="small" style="margin-right: 4px">{{ ROLE_NAME[r] || r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Status" width="90">
          <template #default="{ row }"><StatusPill :value="row.is_active" /></template>
        </el-table-column>
        <el-table-column label="Last sign-in" min-width="170">
          <template #default="{ row }">{{ datetime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="Creation Time" min-width="170">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
            <el-button link type="primary" @click="resetPwd(row)">Reset password</el-button>
            <template v-if="!isBuiltinOps(row)">
              <el-button link @click="toggle(row)">{{ row.is_active ? 'Deactivate' : 'Activate' }}</el-button>
              <el-button link type="danger" @click="remove(row)">Delete</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-table v-else-if="activeView === 'logs'" :data="logRows" v-loading="loading">
        <el-table-column prop="username" label="Operator" min-width="120" />
        <el-table-column label="Action type" min-width="110">
          <template #default="{ row }">{{ LOG_ACTION[row.action] || row.action || '—' }}</template>
        </el-table-column>
        <el-table-column prop="resource" label="Resource" min-width="120" />
        <el-table-column label="Resource ID" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.resource_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="Action detail" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ logDetail(row.detail) }}</template>
        </el-table-column>
        <el-table-column label="Status" width="90">
          <template #default="{ row }">
            <el-tag :type="LOG_STATUS_TYPE[row.status] || 'info'" size="small">
              {{ LOG_STATUS[row.status] || row.status || '—' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="IP address" min-width="130">
          <template #default="{ row }">{{ row.ip_address || '—' }}</template>
        </el-table-column>
        <el-table-column label="Action time" min-width="170">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-table v-else-if="activeView === 'endUsers'" :data="endRows" v-loading="loading">
        <el-table-column prop="username" label="Username" min-width="120" />
        <el-table-column prop="real_name" label="Legal name" min-width="120" />
        <el-table-column prop="email" label="Email" min-width="180" />
        <el-table-column prop="phone" label="Mobile number" min-width="130" />
        <el-table-column prop="merchant_name" label="Linked customer" min-width="140" />
        <el-table-column label="Onboarding" width="110">
          <template #default="{ row }"><StatusPill kind="onboarding" :value="row.onboarding_status" /></template>
        </el-table-column>
        <el-table-column label="Status" width="90">
          <template #default="{ row }"><StatusPill :value="row.is_active" /></template>
        </el-table-column>
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link @click="toggleEnd(row)">{{ row.is_active ? 'Deactivate' : 'Activate' }}</el-button>
            <el-button link type="danger" @click="removeEnd(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-table v-else-if="activeView === 'accounts'" :data="accountRows" v-loading="loading">
        <el-table-column prop="user_id" label="End-user ID" min-width="200" show-overflow-tooltip />
        <el-table-column prop="account_no" label="Account no." min-width="130" />
        <el-table-column prop="account_holder" label="Account holder" min-width="120" />
        <el-table-column label="Bank" min-width="200">
          <template #default="{ row }">{{ row.bank_code ? `${row.bank_code} / ${row.bank_name || '—'}` : (row.bank_name || '—') }}</template>
        </el-table-column>
        <el-table-column prop="merchant_name" label="Linked customer" min-width="150" />
        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="ACCOUNT_STATUS_TYPE[row.status] || 'info'" size="small">
              {{ ACCOUNT_STATUS[row.status] || row.status || '—' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Linked at" min-width="170">
          <template #default="{ row }">{{ datetime(row.bind_at) }}</template>
        </el-table-column>
      </el-table>
      <el-table v-else :data="paymentRows" v-loading="loading">
        <el-table-column prop="order_no" label="Order reference" min-width="180" />
        <el-table-column prop="merchant_name" label="Linked customer" min-width="150" />
        <el-table-column label="Payment amount" min-width="130">
          <template #default="{ row }">{{ money(row.amount) }} {{ row.currency || '' }}</template>
        </el-table-column>
        <el-table-column label="Payment method" width="110">
          <template #default="{ row }">{{ PAY_METHOD[row.pay_method] || row.pay_method || '—' }}</template>
        </el-table-column>
        <el-table-column label="Order status" width="110">
          <template #default="{ row }"><StatusPill :value="row.order_status" /></template>
        </el-table-column>
        <el-table-column label="Payment time" min-width="170">
          <template #default="{ row }">{{ datetime(row.pay_time) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>

    <el-dialog v-model="visible" :title="form.id ? 'Edit user' : 'New user'" width="480px">
      <el-form :model="form" label-width="130px">
        <el-form-item label="Username"><el-input v-model="form.username" :disabled="!!form.id" /></el-form-item>
        <el-form-item v-if="!form.id" label="Password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="Legal name"><el-input v-model="form.real_name" /></el-form-item>
        <el-form-item label="Email"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="Mobile"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="Role">
          <el-select v-model="form.role_codes" multiple style="width: 100%">
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusPill from '@/components/StatusPill.vue'
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
  toggleUserStatus,
  assignUserRoles,
  getRoles,
  getOperationLogs,
  getEndUsers,
  toggleEndUser,
  deleteEndUser
} from '@/api/rbac'
import { getUserAccounts, getUserPayments } from '@/api/userPortal'
import { datetime, money, unwrapList, PAY_METHOD, ROLE_NAME } from '@/utils/format'

const tab = ref('ops')
const opsTab = ref('opsUsers')
const endTab = ref('endUsers')
const activeView = computed(() => tab.value === 'ops' ? opsTab.value : endTab.value)
const searchable = computed(() => ['opsUsers', 'logs', 'endUsers'].includes(activeView.value))
const searchPlaceholder = computed(() => activeView.value === 'logs' ? 'Operator username' : 'Name / username')
const rows = ref([])
const endRows = ref([])
const logRows = ref([])
const accountRows = ref([])
const paymentRows = ref([])
const roles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ search: '' })
const visible = ref(false)
const form = reactive({ id: '', username: '', password: '', real_name: '', email: '', phone: '', role_codes: [] })

const LOG_ACTION = {
  LOGIN: 'Sign-in',
  LOGOUT: 'Sign-out',
  CREATE: 'Create',
  UPDATE: 'Update',
  DELETE: 'Delete',
  APPROVE: 'Approve',
  EXPORT: 'Export'
}
const LOG_STATUS = { SUCCESS: 'Success', FAILED: 'Failed' }
const LOG_STATUS_TYPE = { SUCCESS: 'success', FAILED: 'danger' }
const ACCOUNT_STATUS = { PENDING: 'Pending verification', ACTIVE: 'Linked', EXPIRED: 'Expired', REVOKED: 'Unlinked' }
const ACCOUNT_STATUS_TYPE = { PENDING: 'warning', ACTIVE: 'success', EXPIRED: 'info', REVOKED: 'info' }

async function load() {
  loading.value = true
  try {
    if (activeView.value === 'opsUsers') {
      const data = await getUsers({ page: page.value, page_size: pageSize, search: filters.search || undefined })
      const u = unwrapList(data)
      rows.value = u.rows
      total.value = u.total
    } else if (activeView.value === 'logs') {
      const data = await getOperationLogs({ page: page.value, page_size: pageSize, username: filters.search || undefined })
      const u = unwrapList(data)
      logRows.value = u.rows
      total.value = u.total
    } else if (activeView.value === 'endUsers') {
      const data = await getEndUsers({ page: page.value, page_size: pageSize, search: filters.search || undefined })
      const u = unwrapList(data)
      endRows.value = u.rows
      total.value = u.total
    } else if (activeView.value === 'accounts') {
      const data = await getUserAccounts({ page: page.value, page_size: pageSize })
      const u = unwrapList(data)
      accountRows.value = u.rows
      total.value = u.total
    } else {
      const data = await getUserPayments({ page: page.value, page_size: pageSize })
      const u = unwrapList(data)
      paymentRows.value = u.rows
      total.value = u.total
    }
  } finally {
    loading.value = false
  }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function isBuiltinOps(row) {
  return (row?.username || '') === 'admin'
}
function openCreate() {
  Object.assign(form, { id: '', username: '', password: '', real_name: '', email: '', phone: '', role_codes: [] })
  visible.value = true
}
function openEdit(row) {
  Object.assign(form, { id: row.id, username: row.username, password: '', real_name: row.real_name, email: row.email, phone: row.phone, role_codes: [...(row.roles || [])] })
  visible.value = true
}
async function resetPwd(row) {
  const { value } = await ElMessageBox.prompt(`Enter a new password for ${row.username}`, 'Reset password', {
    inputType: 'password',
    inputPattern: /^.{6,}$/,
    inputErrorMessage: 'The password must contain at least 6 characters.',
    confirmButtonText: 'Reset',
    cancelButtonText: 'Cancel'
  })
  await resetUserPassword(row.id, { new_password: value })
  ElMessage.success('The password has been reset.')
}
async function save() {
  if (!form.id) {
    if (!form.username || !form.password) {
      ElMessage.warning('Username and password are required.')
      return
    }
    await createUser({
      username: form.username,
      password: form.password,
      real_name: form.real_name,
      email: form.email,
      phone: form.phone,
      role_codes: form.role_codes
    })
  } else {
    await updateUser(form.id, { real_name: form.real_name, email: form.email, phone: form.phone })
    await assignUserRoles(form.id, { role_codes: form.role_codes })
  }
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}
async function toggle(row) {
  await toggleUserStatus(row.id)
  load()
}
async function remove(row) {
  await ElMessageBox.confirm(`Delete user ${row.username}?`, 'Confirmation', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('The record has been deleted.')
  load()
}
async function toggleEnd(row) {
  await toggleEndUser(row.id)
  load()
}
async function removeEnd(row) {
  await ElMessageBox.confirm(`Delete end user ${row.username}?`, 'Confirmation', { type: 'warning' })
  await deleteEndUser(row.id)
  load()
}
function logDetail(detail) {
  if (detail === null || detail === undefined || detail === '') return '—'
  if (typeof detail === 'string') return detail
  const text = JSON.stringify(detail)
  return text === '{}' ? '—' : text
}

onMounted(async () => {
  const r = await getRoles({ page_size: 50 })
  const allowed = new Set(['super_admin', 'maker', 'checker', 'authoriser'])
  roles.value = unwrapList(r).rows.filter((item) => allowed.has(item.code))
  load()
})
</script>
