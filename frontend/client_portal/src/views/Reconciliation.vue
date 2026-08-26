<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="tab">
      <el-tab-pane label="对账批次" name="batches">
        <div class="toolbar">
          <el-button type="primary" @click="loadBatches">刷新</el-button>
        </div>
        <el-table :data="batches" v-loading="loadingBatches" border stripe>
          <el-table-column prop="batch_no" label="批次号" min-width="200" />
          <el-table-column prop="bank_name" label="银行" min-width="160" />
          <el-table-column prop="match_count" label="匹配数" min-width="100" />
          <el-table-column prop="diff_count" label="差异数" min-width="100" />
          <el-table-column prop="status" label="状态" min-width="120" />
        </el-table>
        <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="batchTotal" :page-size="pageSize" :current-page="batchPage" @current-change="onBatchPage" />
      </el-tab-pane>

      <el-tab-pane label="对账差异" name="diffs">
        <div class="toolbar">
          <el-button type="primary" @click="loadDiffs">刷新</el-button>
        </div>
        <el-table :data="diffs" v-loading="loadingDiffs" border stripe>
          <el-table-column v-for="col in diffColumns" :key="col" :prop="col" :label="col" min-width="140" />
        </el-table>
        <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="diffTotal" :page-size="pageSize" :current-page="diffPage" @current-change="onDiffPage" />
      </el-tab-pane>

      <el-tab-pane label="Nostro 余额核对" name="nostro">
        <div class="toolbar">
          <el-button type="primary" @click="loadNostro">刷新</el-button>
        </div>
        <el-table :data="nostro" v-loading="loadingNostro" border stripe>
          <el-table-column v-for="col in nostroColumns" :key="col" :prop="col" :label="col" min-width="140" />
        </el-table>
        <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="nostroTotal" :page-size="pageSize" :current-page="nostroPage" @current-change="onNostroPage" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getReconBatches, getReconDiffs, getNostroChecks } from '@/api/reconciliation'

const tab = ref('batches')
const pageSize = ref(20)

const batches = ref([])
const batchTotal = ref(0)
const batchPage = ref(1)
const loadingBatches = ref(false)

const diffs = ref([])
const diffTotal = ref(0)
const diffPage = ref(1)
const loadingDiffs = ref(false)
const diffColumns = ref([])

const nostro = ref([])
const nostroTotal = ref(0)
const nostroPage = ref(1)
const loadingNostro = ref(false)
const nostroColumns = ref([])

async function loadBatches() {
  loadingBatches.value = true
  try {
    const data = await getReconBatches({ page: batchPage.value, page_size: pageSize.value })
    batches.value = data.results || []
    batchTotal.value = data.count || 0
  } finally {
    loadingBatches.value = false
  }
}
async function loadDiffs() {
  loadingDiffs.value = true
  try {
    const data = await getReconDiffs({ page: diffPage.value, page_size: pageSize.value })
    diffs.value = data.results || []
    diffTotal.value = data.count || 0
    diffColumns.value = diffs.value.length ? Object.keys(diffs.value[0]) : []
  } finally {
    loadingDiffs.value = false
  }
}
async function loadNostro() {
  loadingNostro.value = true
  try {
    const data = await getNostroChecks({ page: nostroPage.value, page_size: pageSize.value })
    nostro.value = data.results || []
    nostroTotal.value = data.count || 0
    nostroColumns.value = nostro.value.length ? Object.keys(nostro.value[0]) : []
  } finally {
    loadingNostro.value = false
  }
}
function onBatchPage(p) {
  batchPage.value = p
  loadBatches()
}
function onDiffPage(p) {
  diffPage.value = p
  loadDiffs()
}
function onNostroPage(p) {
  nostroPage.value = p
  loadNostro()
}

onMounted(() => {
  loadBatches()
  loadDiffs()
  loadNostro()
})
</script>
