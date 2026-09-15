<template>
  <div>
    <PageHeader :title="headerTitle" subtitle="Transaction counts and fee share by currency">
      <el-button @click="goBack">Back</el-button>
      <el-button type="primary" :disabled="!overview" @click="openEdit">Edit share</el-button>
    </PageHeader>
    <KpiCards :items="kpis" />
    <div class="page-card">
      <h3 class="section-title">By currency</h3>
      <el-table :data="overview?.by_currency || []" v-loading="loading">
        <el-table-column prop="currency" label="Currency" min-width="100" />
        <el-table-column prop="order_count" label="Orders" width="100" />
        <el-table-column label="Volume" min-width="140">
          <template #default="{ row }">{{ money(row.volume) }}</template>
        </el-table-column>
        <el-table-column label="Customer fees" min-width="140">
          <template #default="{ row }">{{ money(row.customer_fee) }}</template>
        </el-table-column>
        <el-table-column label="Agent share" min-width="140">
          <template #default="{ row }">{{ money(row.agent_fee) }}</template>
        </el-table-column>
      </el-table>
    </div>
    <div class="page-card" style="margin-top: 16px">
      <h3 class="section-title">Recent transactions</h3>
      <el-table :data="overview?.recent_orders || []" v-loading="loading">
        <el-table-column prop="order_no" label="Order" min-width="160" />
        <el-table-column prop="customer_name" label="Customer" min-width="150" />
        <el-table-column prop="currency" label="Currency" width="100" />
        <el-table-column label="Amount" min-width="120">
          <template #default="{ row }">{{ money(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="Fee" min-width="110">
          <template #default="{ row }">{{ money(row.fee_amount) }}</template>
        </el-table-column>
        <el-table-column label="Agent share" min-width="120">
          <template #default="{ row }">{{ money(row.agent_fee) }}</template>
        </el-table-column>
        <el-table-column label="Status" width="150">
          <template #default="{ row }"><StatusPill :value="row.status" /></template>
        </el-table-column>
        <el-table-column label="Created" min-width="165">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="Edit share" width="420px">
      <el-form label-width="120px">
        <el-form-item label="Share of fee">
          <el-input-number v-model="sharePercentInput" :min="0" :max="100" :precision="2" :step="1" />
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getAgentFeeOverview, updateAgent } from '@/api/agents'
import { datetime, money } from '@/utils/format'

function sharePercent(rate) {
  const n = Number(rate)
  if (Number.isNaN(n)) return 0
  return Math.round(n * 10000) / 100
}

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const overview = ref(null)
const visible = ref(false)
const sharePercentInput = ref(0)

const headerTitle = computed(() => {
  if (!overview.value) return 'Agent Fee'
  return `${overview.value.agent_name} · ${sharePercent(overview.value.commission_rate)}%`
})
const kpis = computed(() => {
  const data = overview.value || {}
  return [
    { label: 'Share', value: `${sharePercent(data.commission_rate)}%` },
    { label: 'Customers', value: data.customer_count ?? 0 },
    { label: 'Orders', value: data.order_count ?? 0 },
    { label: 'Currencies', value: data.currency_count ?? 0 },
  ]
})

async function load() {
  loading.value = true
  try {
    overview.value = await getAgentFeeOverview(route.params.id)
  } finally {
    loading.value = false
  }
}
function goBack() {
  router.push('/agent-fees')
}
function openEdit() {
  sharePercentInput.value = sharePercent(overview.value?.commission_rate)
  visible.value = true
}
async function save() {
  await updateAgent(route.params.id, { commission_rate: (Number(sharePercentInput.value) / 100).toFixed(6) })
  ElMessage.success('The share has been saved.')
  visible.value = false
  load()
}
watch(() => route.params.id, () => { if (route.params.id) load() })
onMounted(load)
</script>

<style scoped>
.section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}
.share-suffix {
  margin-left: 8px;
  color: var(--tech-muted);
}
</style>
