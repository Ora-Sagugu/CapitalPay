<template>
  <div>
    <PageHeader title="Profiles" subtitle="Agent profiles, settlement banks and onboarding agreement" />
    <el-tabs v-model="activeTab">
      <el-tab-pane label="Agent profiles" name="agents" />
      <el-tab-pane label="Customers" name="merchants" />
      <el-tab-pane label="Onboarding" name="onboarding" />
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
            <el-button link type="primary" @click="viewRelations(row)">Customers</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <div v-else-if="activeTab === 'merchants'" class="page-card">
      <div class="toolbar">
        <el-input v-model="relationFilters.agent_no" placeholder="Agent Code" clearable style="width: 180px" @keyup.enter="queryRelations" />
        <el-input v-model="relationFilters.search" placeholder="Customer name / number" clearable style="width: 220px" @keyup.enter="queryRelations" />
        <el-button type="primary" @click="queryRelations">Search</el-button>
        <el-button @click="resetRelationFilters">Reset</el-button>
      </div>
      <el-table :data="relationRows" v-loading="relationLoading">
        <el-table-column type="index" label="#" width="55" :index="relationIndex" />
        <el-table-column prop="agent_name" label="Agent" min-width="150" />
        <el-table-column prop="agent_no" label="Agent Code" min-width="130" />
        <el-table-column prop="customer_no" label="Customer no." min-width="140" />
        <el-table-column prop="legal_name" label="Customer" min-width="160" />
        <el-table-column prop="kyc_status" label="KYC" min-width="110" />
        <el-table-column prop="contact_name" label="Contact" min-width="120" />
        <el-table-column prop="contact_email" label="Email" min-width="180" />
        <el-table-column label="Creation Time" min-width="165">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
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
    <div v-else-if="activeTab === 'onboarding'">
      <KycReview embedded portal-role="agent" />
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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
  getAgentCustomers
} from '@/api/agents'
import { unwrapList, datetime } from '@/utils/format'
import { useAuthStore } from '@/store/auth'
import KycReview from '@/views/KycReview.vue'

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
const relationFilters = reactive({ agent_no: '', search: '' })
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

function relationIndex(index) {
  return (relationPage.value - 1) * relationPageSize.value + index + 1
}
async function loadRelations() {
  relationLoading.value = true
  try {
    const data = unwrapList(await getAgentCustomers({
      page: relationPage.value,
      page_size: relationPageSize.value,
      search: relationFilters.search || undefined,
      agent__agent_no: relationFilters.agent_no || undefined
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
  relationFilters.search = ''
  queryRelations()
}
function onRelationPage(page) {
  relationPage.value = page
  loadRelations()
}
function viewRelations(row) {
  relationFilters.agent_no = row.agent_no
  relationFilters.search = ''
  relationPage.value = 1
  activeTab.value = 'merchants'
}
watch(activeTab, (value) => {
  if (value === 'merchants') loadRelations()
})
onMounted(load)
</script>
