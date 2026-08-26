<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-select v-model="filters.base" placeholder="基准币种" clearable style="width: 120px">
        <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="filters.quote" placeholder="目标币种" clearable style="width: 120px">
        <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button type="success" @click="openCreate">手动新增</el-button>
      <el-button @click="doImportDaily">导入当日</el-button>
      <el-button @click="doSync">同步市场</el-button>
      <el-upload :show-file-list="false" :http-request="uploadCsv" accept=".csv">
        <el-button>CSV 导入</el-button>
      </el-upload>
    </div>

    <el-table :data="pagedRows" v-loading="loading" border stripe>
      <el-table-column prop="from_currency" label="基准" width="90" />
      <el-table-column prop="to_currency" label="目标" width="90" />
      <el-table-column prop="rate" label="汇率(8位)" min-width="160" />
      <el-table-column prop="date" label="生效日期" min-width="140" />
      <el-table-column prop="source" label="来源" min-width="120" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />

    <el-dialog v-model="dlg" :title="editingId ? '编辑汇率' : '新增汇率'" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="日期"><el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="基准币种"><el-select v-model="form.from_currency" style="width: 100%"><el-option v-for="c in currencies" :key="c" :label="c" :value="c" /></el-select></el-form-item>
        <el-form-item label="目标币种"><el-select v-model="form.to_currency" style="width: 100%"><el-option v-for="c in currencies" :key="c" :label="c" :value="c" /></el-select></el-form-item>
        <el-form-item label="汇率"><el-input v-model="form.rate" placeholder="最多 8 位小数" /></el-form-item>
        <el-form-item label="数据源">
          <el-select v-model="form.source" style="width: 100%">
            <el-option v-for="s in sources" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getExchangeRates, createExchangeRate, updateExchangeRate,
  importDailyRates, syncRealtimeRates, importCsvRates
} from '@/api/exchange'

const currencies = ['USD', 'CNY', 'HKD', 'EUR', 'GBP', 'JPY']
const sources = ['Manual', 'Reuters', 'Bloomberg', 'XE', '中国银行', '工商银行']
const allRows = ref([])
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ base: '', quote: '' })
const dlg = ref(false)
const editingId = ref(null)
const form = reactive({ date: '', from_currency: 'USD', to_currency: 'CNY', rate: '', source: 'Manual' })

const filtered = computed(() => {
  return allRows.value.filter((r) => {
    if (filters.base && r.from_currency !== filters.base) return false
    if (filters.quote && r.to_currency !== filters.quote) return false
    return true
  })
})
const total = computed(() => filtered.value.length)
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

async function load() {
  loading.value = true
  try {
    const data = await getExchangeRates({})
    allRows.value = Array.isArray(data) ? data : (data.results || [])
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  load()
}
function onPage(p) {
  page.value = p
}
function openCreate() {
  editingId.value = null
  Object.assign(form, { date: new Date().toISOString().slice(0, 10), from_currency: 'USD', to_currency: 'CNY', rate: '', source: 'Manual' })
  dlg.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { date: row.date, from_currency: row.from_currency, to_currency: row.to_currency, rate: row.rate, source: row.source })
  dlg.value = true
}
async function save() {
  if (editingId.value) await updateExchangeRate(editingId.value, { ...form })
  else await createExchangeRate({ ...form })
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function doImportDaily() {
  await importDailyRates({ overwrite: true })
  ElMessage.success('已导入当日汇率')
  load()
}
async function doSync() {
  try {
    await syncRealtimeRates({ source: 'Bloomberg' })
    ElMessage.success('已同步')
  } catch {
    ElMessage.info('实时源未配置时使用 MOCK/导入当日即可')
  }
  load()
}
async function uploadCsv({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  await importCsvRates(fd)
  ElMessage.success('CSV 已导入')
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
</style>
