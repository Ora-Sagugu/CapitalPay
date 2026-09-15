<template>
  <div>
    <PageHeader title="Pre-orders" subtitle="Approved instructions awaiting correspondent clearing" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Order reference / PRN / customer" clearable style="width: 220px" />
        <el-select v-model="filters.from_currency" placeholder="Source currency" clearable style="width: 120px">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-select v-model="filters.to_currency" placeholder="Destination currency" clearable style="width: 120px">
          <el-option v-for="c in CURRENCIES" :key="c.value" :label="c.value" :value="c.value" />
        </el-select>
        <el-button type="primary" @click="reload">Search</el-button>
        <el-button @click="reset">Reset</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="order_no" label="Order reference" min-width="170" />
        <el-table-column prop="prn_code" label="PRN" min-width="110" />
        <el-table-column prop="merchant_name" label="Customer" min-width="140" />
        <el-table-column prop="from_currency" label="Source" min-width="90" />
        <el-table-column prop="to_currency" label="Destination" min-width="110" />
        <el-table-column prop="fee_amount" label="Charges" min-width="90" :formatter="formatMoneyCell" />
        <el-table-column prop="beneficiary_name" label="Beneficiary" min-width="120" />
        <el-table-column label="Status" width="110"><template #default="{ row }"><StatusPill :value="row.status" /></template></el-table-column>
        <el-table-column label="Creation Time" min-width="160"><template #default="{ row }">{{ datetime(row.created_at) }}</template></el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getPreorders, getPreorderStats } from '@/api/orders'
import { unwrapList, datetime, CURRENCIES, money, formatMoneyCell } from '@/utils/format'

const rows = ref([])
const stats = ref({})
const loading = ref(false)
const filters = reactive({ search: '', from_currency: '', to_currency: '' })
const kpis = computed(() => [
  { label: 'Instructions pending clearing', value: stats.value.total_count ?? 0 },
  { label: 'Aggregate amount pending clearing', value: money(stats.value.total_amount) },
  { label: 'Aggregate charges', value: money(stats.value.total_fee) },
  { label: 'Created today', value: stats.value.today_count ?? 0 }
])
async function load() {
  loading.value = true
  try {
    stats.value = await getPreorderStats()
    const data = await getPreorders({ ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })
    rows.value = unwrapList(data).rows
  } finally { loading.value = false }
}
function reload() { load() }
function reset() { Object.assign(filters, { search: '', from_currency: '', to_currency: '' }); load() }
onMounted(load)
</script>
