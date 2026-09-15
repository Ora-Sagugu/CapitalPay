<template>
  <div>
    <PageHeader title="Agent Fee" subtitle="Share of customer transaction fees, by agent" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Agent / code" clearable style="width: 220px" @keyup.enter="reload" />
        <el-select v-model="filters.status" placeholder="Status" clearable style="width: 130px" @change="reload">
          <el-option label="Active" value="ACTIVE" />
          <el-option label="Suspended" value="SUSPENDED" />
          <el-option label="Closed" value="CLOSED" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="agent_name" label="Agent" min-width="180" />
        <el-table-column prop="agent_no" label="Agent Code" min-width="130" />
        <el-table-column label="Share" width="110">
          <template #default="{ row }">{{ formatShare(row.commission_rate) }}</template>
        </el-table-column>
        <el-table-column prop="customer_count" label="Customers" width="110" />
        <el-table-column prop="order_count" label="Orders" width="100" />
        <el-table-column label="Status" width="100">
          <template #default="{ row }"><StatusPill kind="agent" :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Actions" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit share</el-button>
            <el-button link type="primary" @click="openDetail(row)">View</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="Edit share" width="420px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Agent">{{ form.agent_name }}</el-form-item>
        <el-form-item label="Share of fee">
          <el-input-number v-model="form.share_percent" :min="0" :max="100" :precision="2" :step="1" />
          <span class="share-suffix">%</span>
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
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getAgents, updateAgent } from '@/api/agents'
import { unwrapList } from '@/utils/format'

function sharePercent(rate) {
  const n = Number(rate)
  if (Number.isNaN(n)) return 0
  return Math.round(n * 10000) / 100
}
function formatShare(rate) {
  return `${sharePercent(rate)}%`
}

const router = useRouter()
const rows = ref([])
const loading = ref(false)
const filters = reactive({ search: '', status: '' })
const visible = ref(false)
const form = reactive({ id: '', agent_name: '', share_percent: 0 })

const kpis = computed(() => {
  const list = rows.value
  const avg = list.length
    ? list.reduce((sum, row) => sum + sharePercent(row.commission_rate), 0) / list.length
    : 0
  return [
    { label: 'Agents', value: list.length },
    { label: 'Average share', value: `${avg.toFixed(1)}%` },
    { label: 'Customers', value: list.reduce((sum, row) => sum + Number(row.customer_count || 0), 0) },
    { label: 'Orders', value: list.reduce((sum, row) => sum + Number(row.order_count || 0), 0) },
  ]
})

async function load() {
  loading.value = true
  try {
    const params = { page_size: 100 }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    rows.value = unwrapList(await getAgents(params)).rows
  } finally {
    loading.value = false
  }
}
function reload() { load() }
function openDetail(row) {
  router.push(`/agent-fees/${row.id}`)
}
function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    agent_name: row.agent_name,
    share_percent: sharePercent(row.commission_rate),
  })
  visible.value = true
}
async function save() {
  await updateAgent(form.id, { commission_rate: (Number(form.share_percent) / 100).toFixed(6) })
  ElMessage.success('The share has been saved.')
  visible.value = false
  load()
}
onMounted(load)
</script>

<style scoped>
.share-suffix {
  margin-left: 8px;
  color: var(--tech-muted);
}
</style>
