<template>
  <div>
    <PageHeader title="Screening" subtitle="Remittance and manual sanctions screening" />
    <div class="page-card">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="Screening records" name="scans">
          <div class="toolbar">
            <el-input v-model="scanFilters.search" placeholder="Screening number / target" clearable style="width: 220px" @keyup.enter="reloadScans" />
            <el-select v-model="scanFilters.status" placeholder="Screening status" clearable style="width: 140px" @change="reloadScans">
              <el-option label="Pending" value="PENDING" />
              <el-option label="In progress" value="SCANNING" />
              <el-option label="Hit" value="HIT" />
              <el-option label="Clear" value="CLEAR" />
              <el-option label="Manual review" value="MANUAL_REVIEW" />
            </el-select>
            <el-button @click="reloadScans">Refresh</el-button>
            <el-button type="primary" :loading="fullScanLoading" @click="runFullScan">Full screening</el-button>
            <el-button @click="openScan">Run screening</el-button>
          </div>
          <el-table :data="scanRows" v-loading="scanLoading">
            <el-table-column prop="scan_no" label="Screening number" min-width="180" />
            <el-table-column prop="target_name" label="Screening target" min-width="160" />
            <el-table-column prop="target_type" label="Target type" width="110" />
            <el-table-column prop="scan_type" label="Screening type" width="110" />
            <el-table-column label="Status" width="100">
              <template #default="{ row }">
                <el-tag :type="scanStatusType(row)">{{ scanStatusLabel(row) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="hit_count" label="Hit count" min-width="100" />
            <el-table-column label="Screened at" min-width="170">
              <template #default="{ row }">{{ datetime(row.created_at || row.scanned_at) }}</template>
            </el-table-column>
            <el-table-column label="Actions" width="100" fixed="right">
              <template #default="{ row }">
                <el-button v-if="Number(row.hit_count) > 0" link type="danger" @click="viewHits(row)">View hits</el-button>
                <span v-else>—</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="toolbar list-pagination"
            background
            layout="total, prev, pager, next"
            :total="scanTotal"
            :page-size="pageSize"
            :current-page="scanPage"
            @current-change="onScanPage"
          />
        </el-tab-pane>

        <el-tab-pane label="Hit details" name="hits">
          <div class="toolbar">
            <el-input v-model="hitFilters.scanNo" placeholder="Screening number" clearable style="width: 220px" @keyup.enter="reloadHits" />
            <el-select v-model="hitFilters.resolution" placeholder="Disposition" clearable style="width: 140px" @change="reloadHits">
              <el-option label="Pending" value="PENDING" />
              <el-option label="Confirmed hit" value="TRUE_HIT" />
              <el-option label="False positive" value="FALSE_POSITIVE" />
            </el-select>
            <el-button @click="reloadHits">Refresh</el-button>
          </div>
          <el-table :data="hitRows" v-loading="hitLoading">
            <el-table-column prop="scan_record" label="Scan ID" width="110" />
            <el-table-column prop="entity_name" label="Matched entity" min-width="170" />
            <el-table-column prop="list_type" label="List source" width="120" />
            <el-table-column label="Risk level" min-width="110">
              <template #default="{ row }"><StatusPill kind="risk" :value="row.risk_level" /></template>
            </el-table-column>
            <el-table-column prop="match_field" label="Match field" min-width="130" />
            <el-table-column prop="match_value" label="Match value" min-width="170" />
            <el-table-column label="Match score" min-width="110">
              <template #default="{ row }">{{ formatScore(row.match_score) }}</template>
            </el-table-column>
            <el-table-column label="Disposition" width="110">
              <template #default="{ row }">
                <el-tag :type="resolutionType(row.resolution)">{{ resolutionLabel(row.resolution) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Hit time" min-width="170">
              <template #default="{ row }">{{ datetime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="toolbar list-pagination"
            background
            layout="total, prev, pager, next"
            :total="hitTotal"
            :page-size="pageSize"
            :current-page="hitPage"
            @current-change="onHitPage"
          />
        </el-tab-pane>
      </el-tabs>
    </div>
    <el-dialog v-model="visible" title="Run screening" width="440px">
      <el-form :model="form" label-width="130px">
        <el-form-item label="Target"><el-input v-model="form.target_name" /></el-form-item>
        <el-form-item label="Address"><el-input v-model="form.address" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" :loading="manualScanLoading" @click="run">Execute</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import StatusPill from '@/components/StatusPill.vue'
import { getSanctionScans, createSanctionScan, getSanctionHits } from '@/api/compliance'
import { unwrapList, datetime } from '@/utils/format'

const pageSize = 20
const activeTab = ref('scans')
const scanRows = ref([])
const scanTotal = ref(0)
const scanPage = ref(1)
const scanLoading = ref(false)
const hitRows = ref([])
const hitTotal = ref(0)
const hitPage = ref(1)
const hitLoading = ref(false)
const fullScanLoading = ref(false)
const manualScanLoading = ref(false)
const visible = ref(false)
const scanFilters = reactive({ search: '', status: '' })
const hitFilters = reactive({ scanNo: '', resolution: '' })
const form = reactive({ target_name: '', address: '' })

const scanStatuses = {
  PENDING: { label: 'Pending', type: 'warning' },
  SCANNING: { label: 'In progress', type: 'primary' },
  CLEAR: { label: 'Clear', type: 'success' },
  HIT: { label: 'Hit', type: 'danger' },
  MANUAL_REVIEW: { label: 'Manual review', type: 'warning' }
}
const resolutions = {
  PENDING: { label: 'Pending', type: 'warning' },
  TRUE_HIT: { label: 'Confirmed hit', type: 'danger' },
  FALSE_POSITIVE: { label: 'False positive', type: 'success' }
}

async function loadScans() {
  scanLoading.value = true
  try {
    const data = await getSanctionScans({
      page: scanPage.value,
      page_size: pageSize,
      search: scanFilters.search || undefined,
      status: scanFilters.status || undefined
    })
    const result = unwrapList(data)
    scanRows.value = result.rows
    scanTotal.value = result.total
  } catch {
    scanRows.value = []
    scanTotal.value = 0
  } finally {
    scanLoading.value = false
  }
}

async function loadHits() {
  hitLoading.value = true
  try {
    const data = await getSanctionHits({
      page: hitPage.value,
      page_size: pageSize,
      scan_record__scan_no: hitFilters.scanNo || undefined,
      resolution: hitFilters.resolution || undefined
    })
    const result = unwrapList(data)
    hitRows.value = result.rows
    hitTotal.value = result.total
  } catch {
    hitRows.value = []
    hitTotal.value = 0
  } finally {
    hitLoading.value = false
  }
}

function reloadScans() {
  scanPage.value = 1
  return loadScans()
}
function reloadHits() {
  hitPage.value = 1
  return loadHits()
}
function onScanPage(page) {
  scanPage.value = page
  loadScans()
}
function onHitPage(page) {
  hitPage.value = page
  loadHits()
}
function onTabChange(name) {
  if (name === 'hits') loadHits()
  else loadScans()
}
function viewHits(row) {
  hitFilters.scanNo = row.scan_no || ''
  hitPage.value = 1
  activeTab.value = 'hits'
  loadHits()
}
function scanStatus(row) {
  if (row.status && scanStatuses[row.status]) return row.status
  return Number(row.hit_count) > 0 ? 'HIT' : 'CLEAR'
}
function scanStatusLabel(row) {
  return scanStatuses[scanStatus(row)]?.label || row.status || 'Unknown'
}
function scanStatusType(row) {
  return scanStatuses[scanStatus(row)]?.type || 'info'
}
function resolutionLabel(value) {
  return resolutions[value]?.label || value || 'Pending'
}
function resolutionType(value) {
  return resolutions[value]?.type || 'info'
}
function formatScore(value) {
  const score = Number(value)
  return Number.isFinite(score) ? `${(score * 100).toFixed(1)}%` : '—'
}
function openScan() { visible.value = true }

async function runFullScan() {
  fullScanLoading.value = true
  try {
    const result = await createSanctionScan({ scan_type: 'FULL' })
    ElMessage.success(`Full screening completed: ${result?.count || 0} entities, ${result?.hit_count || 0} hits.`)
    await reloadScans()
  } catch {
    return
  } finally {
    fullScanLoading.value = false
  }
}

async function run() {
  if (!form.target_name.trim()) {
    ElMessage.warning('Enter the screening target.')
    return
  }
  manualScanLoading.value = true
  try {
    await createSanctionScan({ target_name: form.target_name, address: form.address })
    ElMessage.success('Screening has been executed.')
    visible.value = false
    await reloadScans()
  } catch {
    return
  } finally {
    manualScanLoading.value = false
  }
}
onMounted(loadScans)
</script>

<style scoped>
.list-pagination {
  margin-top: 16px;
  margin-bottom: 0;
}
</style>
