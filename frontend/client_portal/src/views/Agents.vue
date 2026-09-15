<template>
  <div>
    <PageHeader title="Profiles" subtitle="Agent profiles, settlement banks and KYC status" />
    <el-tabs v-model="activeTab">
      <el-tab-pane label="Agent profiles" name="agents" />
      <el-tab-pane label="Agent–customer links" name="merchants" />
    </el-tabs>
    <KpiCards v-if="activeTab === 'agents'" :items="kpis" />
    <div v-if="activeTab === 'agents'" class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Agent / name / legal person / licence no." clearable style="width: 260px" @keyup.enter="reload" />
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 130px" @change="reload">
          <el-option label="Active" value="ACTIVE" /><el-option label="Suspended" value="SUSPENDED" /><el-option label="Closed" value="CLOSED" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
        <el-button type="primary" @click="openCreate">+ New agent</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="agent_name" label="Legal name" min-width="150" />
        <el-table-column prop="legal_person" label="Legal person" min-width="100" />
        <el-table-column prop="business_license_no" label="Licence no." min-width="140" />
        <el-table-column prop="settlement_bank_name" label="Settlement bank" min-width="130" />
        <el-table-column prop="settlement_account_no" label="Corporate account" min-width="140" />
        <el-table-column prop="agent_no" label="Agent Code" min-width="130" />
        <el-table-column prop="swift_code" label="SWIFT" min-width="110" />
        <el-table-column prop="contact_name" label="Contact" min-width="100" />
        <el-table-column label="Status" width="90"><template #default="{ row }"><StatusPill kind="agent" :value="row.status" /></template></el-table-column>
        <el-table-column label="Actions" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canApprove && row.status !== 'ACTIVE'" link type="success" @click="activate(row)">Activate</el-button>
            <el-button v-else-if="canApprove" link type="warning" @click="suspend(row)">Suspend</el-button>
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
            <el-button link type="primary" @click="viewRelations(row)">Customer relationships</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div v-else class="page-card">
      <div class="toolbar">
        <el-input v-model="relationFilters.agent_no" placeholder="Agent Code" clearable style="width: 180px" @keyup.enter="queryRelations" />
        <el-input v-model="relationFilters.merchant_no" placeholder="Customer number" clearable style="width: 180px" @keyup.enter="queryRelations" />
        <el-button type="primary" @click="queryRelations">Search</el-button>
        <el-button @click="resetRelationFilters">Reset</el-button>
        <el-button type="primary" @click="openCreateRelation">+ New relationship</el-button>
      </div>
      <el-table :data="relationRows" v-loading="relationLoading">
        <el-table-column type="index" label="#" width="55" :index="relationIndex" />
        <el-table-column prop="agent_name" label="Agent" min-width="150" />
        <el-table-column prop="merchant_name" label="Customer" min-width="150" />
        <el-table-column prop="commission_rate" label="Commission rate" min-width="110" />
        <el-table-column prop="effective_from" label="Effective date" min-width="110" />
        <el-table-column label="Expiry date" min-width="110">
          <template #default="{ row }">{{ row.effective_to || 'Open-ended' }}</template>
        </el-table-column>
        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="relationStatus(row).type" effect="light">{{ relationStatus(row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Creation Time" min-width="165">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditRelation(row)">Edit</el-button>
            <el-button link type="danger" @click="removeRelation(row)">Terminate</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="relationTotal"
        :page-size="relationPageSize"
        :current-page="relationPage"
        @current-change="onRelationPage"
      />
    </div>
    <el-dialog v-model="visible" :title="form.id ? 'Edit agent' : 'New agent'" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="Agent Code" required>
          <el-input v-model="form.agent_no" maxlength="32" />
        </el-form-item>
        <el-form-item label="Legal name"><el-input v-model="form.agent_name" /></el-form-item>
        <el-form-item label="Legal person"><el-input v-model="form.legal_person" /></el-form-item>
        <el-form-item label="Licence no."><el-input v-model="form.business_license_no" /></el-form-item>
        <el-form-item label="Contact"><el-input v-model="form.contact_name" /></el-form-item>
        <el-form-item label="Settlement bank"><el-input v-model="form.settlement_bank_name" /></el-form-item>
        <el-form-item label="Corporate account"><el-input v-model="form.settlement_account_no" /></el-form-item>
        <el-form-item label="SWIFT"><el-input v-model="form.swift_code" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="relationVisible" :title="relationForm.id ? 'Edit the agent–customer relationship' : 'Create an agent–customer relationship'" width="560px">
      <el-form :model="relationForm" label-width="120px">
        <el-form-item label="Agent" required>
          <el-select
            v-model="relationForm.agent"
            filterable
            remote
            reserve-keyword
            placeholder="Enter agent name or number"
            :remote-method="loadAgentOptions"
            :loading="agentOptionsLoading"
            style="width: 100%"
          >
            <el-option
              v-for="option in agentOptions"
              :key="option.id"
              :label="[option.agent_name, option.agent_no].filter(Boolean).join(' · ')"
              :value="option.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Customer" required>
          <el-select
            v-model="relationForm.merchant"
            filterable
            remote
            reserve-keyword
            placeholder="Enter the customer name or number"
            :remote-method="loadMerchantOptions"
            :loading="merchantOptionsLoading"
            style="width: 100%"
          >
            <el-option
              v-for="option in merchantOptions"
              :key="option.id"
              :label="[option.merchant_name, option.merchant_no].filter(Boolean).join(' · ')"
              :value="option.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Commission rate" required>
          <el-input-number
            v-model="relationForm.commission_rate"
            :min="0"
            :max="1"
            :precision="6"
            :step="0.001"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Effective date" required>
          <el-date-picker v-model="relationForm.effective_from" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Expiry date">
          <el-date-picker v-model="relationForm.effective_to" type="date" value-format="YYYY-MM-DD" clearable style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="relationVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="relationSaving" @click="saveRelation">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import {
  getAgents,
  getAgentStats,
  createAgent,
  updateAgent,
  activateAgent,
  suspendAgent,
  getAgentMerchants,
  createAgentMerchant,
  updateAgentMerchant,
  deleteAgentMerchant
} from '@/api/agents'
import { getMerchants } from '@/api/merchants'
import { unwrapList, datetime } from '@/utils/format'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canApprove = computed(() => auth.hasPermission('feature:agents.approve'))

const activeTab = ref('agents')
const rows = ref([])
const stats = ref({})
const loading = ref(false)
const filters = reactive({ search: '', status: '' })
const visible = ref(false)
const form = reactive({ id: '', agent_no: '', agent_name: '', legal_person: '', business_license_no: '', contact_name: '', settlement_bank_name: '', settlement_account_no: '', swift_code: '' })
const relationRows = ref([])
const relationTotal = ref(0)
const relationPage = ref(1)
const relationPageSize = ref(20)
const relationLoading = ref(false)
const relationFilters = reactive({ agent_no: '', merchant_no: '' })
const relationVisible = ref(false)
const relationSaving = ref(false)
const relationForm = reactive({ id: '', agent: '', merchant: '', commission_rate: 0, effective_from: '', effective_to: '' })
const agentOptions = ref([])
const merchantOptions = ref([])
const agentOptionsLoading = ref(false)
const merchantOptionsLoading = ref(false)
const kpis = computed(() => [
  { label: 'All', value: stats.value.total ?? 0 },
  { label: 'Active', value: stats.value.active ?? 0 },
  { label: 'Suspended', value: stats.value.suspended ?? 0 },
  { label: 'Closed', value: stats.value.closed ?? 0 }
])
async function load() {
  loading.value = true
  try {
    stats.value = await getAgentStats()
    const data = await getAgents({ page_size: 50, search: filters.search || undefined, status: filters.status || undefined })
    rows.value = unwrapList(data).rows
  } catch {
    stats.value = {}
    rows.value = []
  } finally { loading.value = false }
}
function reload() { load() }
function openCreate() { Object.assign(form, { id: '', agent_no: '', agent_name: '', legal_person: '', business_license_no: '', contact_name: '', settlement_bank_name: '', settlement_account_no: '', swift_code: '' }); visible.value = true }
function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    agent_no: row.agent_no,
    agent_name: row.agent_name,
    legal_person: row.legal_person,
    business_license_no: row.business_license_no,
    contact_name: row.contact_name,
    settlement_bank_name: row.settlement_bank_name,
    settlement_account_no: row.settlement_account_no,
    swift_code: row.swift_code
  })
  visible.value = true
}
async function save() {
  const agentNo = String(form.agent_no || '').trim()
  if (!agentNo) {
    ElMessage.warning('Agent Code is required.')
    return
  }
  form.agent_no = agentNo
  const payload = { ...form }
  delete payload.id
  if (form.id) await updateAgent(form.id, payload)
  else await createAgent(payload)
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}
async function activate(row) { await activateAgent(row.id); load() }
async function suspend(row) { await suspendAgent(row.id); load() }

function todayString() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
function relationStatus(row) {
  const today = todayString()
  if (row.effective_from && row.effective_from > today) return { label: 'Pending', type: 'warning' }
  if (row.effective_to && row.effective_to < today) return { label: 'Expired', type: 'info' }
  return { label: 'Active', type: 'success' }
}
function relationIndex(index) {
  return (relationPage.value - 1) * relationPageSize.value + index + 1
}
async function loadRelations() {
  relationLoading.value = true
  try {
    const data = unwrapList(await getAgentMerchants({
      page: relationPage.value,
      page_size: relationPageSize.value,
      agent__agent_no: relationFilters.agent_no || undefined,
      merchant__merchant_no: relationFilters.merchant_no || undefined
    }))
    relationRows.value = data.rows
    relationTotal.value = data.total
  } catch {
    relationRows.value = []
    relationTotal.value = 0
  } finally {
    relationLoading.value = false
  }
}
function queryRelations() {
  relationPage.value = 1
  loadRelations()
}
function resetRelationFilters() {
  relationFilters.agent_no = ''
  relationFilters.merchant_no = ''
  queryRelations()
}
function onRelationPage(page) {
  relationPage.value = page
  loadRelations()
}
function viewRelations(row) {
  relationFilters.agent_no = row.agent_no
  relationFilters.merchant_no = ''
  relationPage.value = 1
  activeTab.value = 'merchants'
}
function resetRelationForm() {
  Object.assign(relationForm, {
    id: '',
    agent: '',
    merchant: '',
    commission_rate: 0,
    effective_from: todayString(),
    effective_to: ''
  })
}
async function loadAgentOptions(keyword = '') {
  const selected = agentOptions.value.find((option) => option.id === relationForm.agent)
  agentOptionsLoading.value = true
  try {
    const options = unwrapList(await getAgents({ search: keyword || undefined })).rows
    if (selected && !options.some((option) => option.id === selected.id)) options.unshift(selected)
    agentOptions.value = options
  } catch {
    agentOptions.value = selected ? [selected] : []
  } finally {
    agentOptionsLoading.value = false
  }
}
async function loadMerchantOptions(keyword = '') {
  const selected = merchantOptions.value.find((option) => option.id === relationForm.merchant)
  merchantOptionsLoading.value = true
  try {
    const options = unwrapList(await getMerchants({ search: keyword || undefined })).rows
    if (selected && !options.some((option) => option.id === selected.id)) options.unshift(selected)
    merchantOptions.value = options
  } catch {
    merchantOptions.value = selected ? [selected] : []
  } finally {
    merchantOptionsLoading.value = false
  }
}
function openCreateRelation() {
  resetRelationForm()
  const presetAgent = rows.value.find((row) => row.agent_no === relationFilters.agent_no)
  if (presetAgent) {
    relationForm.agent = presetAgent.id
    agentOptions.value = [presetAgent]
  } else {
    agentOptions.value = []
  }
  merchantOptions.value = []
  relationVisible.value = true
  loadAgentOptions(presetAgent?.agent_name || '')
  loadMerchantOptions()
}
function openEditRelation(row) {
  Object.assign(relationForm, {
    id: row.id,
    agent: row.agent,
    merchant: row.merchant,
    commission_rate: Number(row.commission_rate || 0),
    effective_from: row.effective_from,
    effective_to: row.effective_to || ''
  })
  agentOptions.value = [{ id: row.agent, agent_name: row.agent_name }]
  merchantOptions.value = [{ id: row.merchant, merchant_name: row.merchant_name }]
  relationVisible.value = true
  loadAgentOptions(row.agent_name)
  loadMerchantOptions(row.merchant_name)
}
async function saveRelation() {
  if (!relationForm.agent || !relationForm.merchant || !relationForm.effective_from) {
    ElMessage.warning('The agent, customer and effective date are required.')
    return
  }
  if (relationForm.effective_to && relationForm.effective_to < relationForm.effective_from) {
    ElMessage.warning('The expiry date cannot precede the effective date.')
    return
  }
  const rate = Number(relationForm.commission_rate)
  if (Number.isNaN(rate) || rate < 0 || rate > 1) {
    ElMessage.warning('The commission rate must be between 0 and 1.')
    return
  }
  const payload = {
    agent: relationForm.agent,
    merchant: relationForm.merchant,
    commission_rate: rate,
    effective_from: relationForm.effective_from,
    effective_to: relationForm.effective_to || null
  }
  relationSaving.value = true
  try {
    if (relationForm.id) await updateAgentMerchant(relationForm.id, payload)
    else await createAgentMerchant(payload)
    ElMessage.success('The agent–customer relationship has been saved.')
    relationVisible.value = false
    await loadRelations()
  } catch {
    // The request layer displays the backend error; keep the dialog open for correction.
  } finally {
    relationSaving.value = false
  }
}
async function removeRelation(row) {
  try {
    await ElMessageBox.confirm(`Confirm termination of the relationship “${row.agent_name} — ${row.merchant_name}”?`, 'Terminate the agent–customer relationship', {
      confirmButtonText: 'Terminate',
      cancelButtonText: 'Cancel',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await deleteAgentMerchant(row.id)
    ElMessage.success('The relationship has been terminated.')
    if (relationRows.value.length === 1 && relationPage.value > 1) relationPage.value -= 1
    await loadRelations()
  } catch {
    // Request errors are reported by the global interceptor.
  }
}
watch(activeTab, (value) => {
  if (value === 'merchants') loadRelations()
})
onMounted(load)
</script>
