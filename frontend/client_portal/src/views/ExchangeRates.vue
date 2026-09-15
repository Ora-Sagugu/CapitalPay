<template>
  <div>
    <PageHeader title="FX Rates" subtitle="Manual entry, bulk import and market sync" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="Start" end-placeholder="End" />
        <el-input v-model="search" placeholder="Search currency / source" clearable style="width: 180px" @keyup.enter="load" />
        <el-upload :show-file-list="false" accept=".csv" :http-request="onCsv">
          <el-button>Bulk import</el-button>
        </el-upload>
        <el-button @click="importDaily">Import today's rates</el-button>
        <el-button @click="syncMarket">Synchronise market rates</el-button>
        <el-button type="primary" @click="openCreate">+ Manual entry</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="date" label="Date" width="120" />
        <el-table-column label="Currency pair" min-width="120">
          <template #default="{ row }">{{ row.from_currency }}/{{ row.to_currency }}</template>
        </el-table-column>
        <el-table-column prop="rate" label="FX rate" min-width="140" />
        <el-table-column label="Source" min-width="130">
          <template #default="{ row }"><el-tag type="success" effect="plain">{{ row.source }}</el-tag></template>
        </el-table-column>
        <el-table-column label="Updated at" min-width="170">
          <template #default="{ row }">{{ datetime(row.updated_at || row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="Manual rate entry" width="440px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="Date"><el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="From"><el-select v-model="form.from_currency" style="width: 100%"><el-option v-for="c in CURRENCIES" :key="c.value" :label="c.label" :value="c.value" /></el-select></el-form-item>
        <el-form-item label="To"><el-select v-model="form.to_currency" style="width: 100%"><el-option v-for="c in CURRENCIES" :key="c.value" :label="c.label" :value="c.value" /></el-select></el-form-item>
        <el-form-item label="Rate"><el-input v-model="form.rate" /></el-form-item>
        <el-form-item label="Source"><el-input v-model="form.source" /></el-form-item>
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
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import { getExchangeRates, getExchangeStats, createExchangeRate, importDailyRates, syncRealtimeRates, importCsvRates } from '@/api/exchange'
import { unwrapList, datetime, CURRENCIES } from '@/utils/format'

const rows = ref([])
const stats = ref({})
const loading = ref(false)
const search = ref('')
const range = ref([])
const visible = ref(false)
const form = reactive({ date: '', from_currency: 'USD', to_currency: 'CNY', rate: '', source: 'Manual' })
const kpis = computed(() => [
  { label: "Today's rates", value: stats.value.today_count ?? 0 },
  { label: 'Currency pairs', value: stats.value.pair_count ?? stats.value.pairs_count ?? 0 },
  { label: 'Data sources', value: stats.value.source_count ?? stats.value.sources_count ?? 0 },
  { label: 'Latest update', value: stats.value.latest_date || '—' }
])
async function load() {
  loading.value = true
  try {
    stats.value = await getExchangeStats()
    const [date_from, date_to] = range.value || []
    const data = await getExchangeRates({ search: search.value || undefined, date_from, date_to })
    rows.value = Array.isArray(data) ? data : unwrapList(data).rows
  } finally { loading.value = false }
}
function openCreate() { visible.value = true }
async function save() {
  await createExchangeRate(form)
  ElMessage.success('The rate has been created.')
  visible.value = false
  load()
}
async function importDaily() { await importDailyRates(); ElMessage.success("Today's rates have been imported."); load() }
async function syncMarket() { await syncRealtimeRates(); ElMessage.success('Market rates have been synchronised.'); load() }
async function onCsv({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  await importCsvRates(fd)
  ElMessage.success('Import completed.')
  load()
}
onMounted(load)
</script>
