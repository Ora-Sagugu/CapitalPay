<template>
  <div>
    <PageHeader title="Lists" subtitle="OFAC and UN sanctions lists" />
    <KpiCards :items="kpis" />
    <div class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.search" placeholder="Entity name / identification number" clearable style="width: 200px" @keyup.enter="reload" />
        <el-select v-model="filters.list_type" placeholder="List source" clearable style="width: 140px" @change="reload">
          <el-option label="OFAC" value="OFAC" /><el-option label="UN" value="UN" />
        </el-select>
        <el-select v-model="filters.risk_level" placeholder="Risk level" clearable style="width: 130px" @change="reload">
          <el-option label="High" value="HIGH" /><el-option label="Medium" value="MEDIUM" /><el-option label="Low" value="LOW" />
        </el-select>
        <el-select v-model="filters.entity_type" placeholder="Entity type" clearable style="width: 150px" @change="reload">
          <el-option v-for="opt in ENTITY_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button @click="reload">Refresh</el-button>
        <el-button type="primary" @click="openImport">Import list</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="entity_name" label="Entity name" min-width="220" show-overflow-tooltip />
        <el-table-column label="Type" width="120">
          <template #default="{ row }">{{ entityTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="list_type" label="List source" width="115" />
        <el-table-column label="Risk level" min-width="115"><template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template></el-table-column>
        <el-table-column prop="country" label="Country" min-width="110" show-overflow-tooltip />
        <el-table-column label="Status" width="90"><template #default="{ row }"><StatusPill :value="row.is_active" /></template></el-table-column>
        <el-table-column prop="effective_date" label="Effective date" min-width="120" />
        <el-table-column prop="review_date" label="Review date" min-width="120" />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
            <el-button link type="danger" @click="remove(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </div>
    <el-dialog v-model="importVisible" title="Import list" width="560px" @closed="resetImport">
      <el-form label-width="110px">
        <el-form-item label="List source">
          <el-select v-model="importForm.list_type" style="width: 100%" @change="clearImportFile">
            <el-option label="OFAC" value="OFAC" />
            <el-option label="UN" value="UN" />
          </el-select>
        </el-form-item>
        <el-form-item label="Official file">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :accept="importAccept"
            :on-change="onImportFileChange"
            :on-remove="clearImportFile"
            :on-exceed="onImportExceed"
          >
            <div class="el-upload__text">Drop the official file here, or <em>click to select</em></div>
            <template #tip>
              <div class="el-upload__tip">{{ importHint }}</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="importForm.reset">Replace existing records of this source</el-checkbox>
        </el-form-item>
        <p class="import-help">
          Download official files:
          <a href="https://www.treasury.gov/ofac/downloads/sdn.csv" target="_blank" rel="noopener">OFAC SDN.CSV</a>
          ·
          <a href="https://scsanctions.un.org/resources/xml/en/consolidated.xml" target="_blank" rel="noopener">UN consolidated.xml</a>
        </p>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="submitImport">Import</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="visible" title="Edit listing" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Entity name"><el-input v-model="form.entity_name" /></el-form-item>
        <el-form-item label="Type">
          <el-select v-model="form.entity_type" style="width: 100%">
            <el-option v-for="opt in ENTITY_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="List source">
          <el-select v-model="form.list_type" style="width: 100%">
            <el-option label="OFAC" value="OFAC" /><el-option label="UN" value="UN" />
          </el-select>
        </el-form-item>
        <el-form-item label="Risk level">
          <el-select v-model="form.risk_level" style="width: 100%">
            <el-option label="High" value="HIGH" /><el-option label="Medium" value="MEDIUM" /><el-option label="Low" value="LOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="Country"><el-input v-model="form.country" /></el-form-item>
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
import KpiCards from '@/components/KpiCards.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getSanctionLists, getSanctionStats, importSanctionFile, updateSanction, deleteSanction } from '@/api/compliance'
import { unwrapList } from '@/utils/format'

const ENTITY_TYPE_OPTIONS = [
  { label: 'Individual', value: 'INDIVIDUAL' },
  { label: 'Entity', value: 'ENTITY' },
  { label: 'Organization', value: 'ORGANIZATION' },
  { label: 'Country', value: 'COUNTRY' },
  { label: 'Region', value: 'REGION' },
]

const LEGACY_ENTITY_TYPE_LABELS = {
  PERSON: 'Individual',
  COMPANY: 'Organization',
  CITY: 'Region',
  VESSEL: 'Entity',
  OTHER: 'Entity',
}

const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const visible = ref(false)
const importVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const uploadRef = ref()
const filters = reactive({ search: '', list_type: '', risk_level: '', entity_type: '' })
const importForm = reactive({ list_type: 'OFAC', reset: false })
const form = reactive({ id: '', entity_name: '', entity_type: 'INDIVIDUAL', list_type: 'OFAC', risk_level: 'HIGH', country: '' })
const kpis = computed(() => [
  { label: 'High risk', value: stats.value.by_risk?.HIGH ?? 0 },
  { label: 'Medium risk', value: stats.value.by_risk?.MEDIUM ?? 0 },
  { label: 'Low risk', value: stats.value.by_risk?.LOW ?? 0 },
  { label: 'Total', value: stats.value.total ?? 0 }
])
const importAccept = computed(() => (importForm.list_type === 'UN' ? '.xml' : '.csv'))
const importHint = computed(() => (
  importForm.list_type === 'UN'
    ? 'Accepts the official UN consolidated.xml only.'
    : 'Accepts the official OFAC SDN.CSV only.'
))

function entityTypeLabel(row) {
  return row.entity_type_display
    || ENTITY_TYPE_OPTIONS.find((opt) => opt.value === row.entity_type)?.label
    || LEGACY_ENTITY_TYPE_LABELS[row.entity_type]
    || row.entity_type
}

async function load() {
  loading.value = true
  try {
    stats.value = await getSanctionStats()
    const data = await getSanctionLists({ page: page.value, page_size: pageSize, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })
    const u = unwrapList(data)
    rows.value = u.rows
    total.value = u.total
  } finally { loading.value = false }
}
function reload() { page.value = 1; load() }
function onPage(p) { page.value = p; load() }
function openImport() {
  resetImport()
  importVisible.value = true
}
function resetImport() {
  importForm.list_type = 'OFAC'
  importForm.reset = false
  clearImportFile()
  importing.value = false
}
function clearImportFile() {
  importFile.value = null
  uploadRef.value?.clearFiles?.()
}
function onImportFileChange(uploadFile) {
  importFile.value = uploadFile?.raw || null
}
function onImportExceed() {
  ElMessage.warning('Select one official file only.')
}
async function submitImport() {
  if (!importFile.value) {
    ElMessage.warning('Select an official sanctions list file.')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    fd.append('list_type', importForm.list_type)
    fd.append('reset', importForm.reset ? 'true' : 'false')
    const result = await importSanctionFile(fd)
    ElMessage.success(`Imported ${result.created ?? 0} ${result.list_type} listing(s).`)
    importVisible.value = false
    reload()
  } finally {
    importing.value = false
  }
}
function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    entity_name: row.entity_name,
    entity_type: row.entity_type,
    list_type: row.list_type,
    risk_level: row.risk_level,
    country: row.country
  })
  visible.value = true
}
async function save() {
  await updateSanction(form.id, { ...form, alias_names: '' })
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}
async function remove(row) {
  await ElMessageBox.confirm('Confirm deletion?', 'Confirmation', { type: 'warning' })
  await deleteSanction(row.id)
  load()
}
onMounted(load)
</script>

<style scoped>
.import-help {
  margin: 0 0 0 110px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.import-help a {
  color: var(--el-color-primary);
}
</style>
