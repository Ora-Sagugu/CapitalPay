<template>
  <el-card class="page-card" shadow="never">
    <el-tabs v-model="mainTab" @tab-change="onMainTab">
      <el-tab-pane label="制裁名单" name="lists" />
      <el-tab-pane label="扫描记录" name="scans" />
      <el-tab-pane label="命中明细" name="hits" />
    </el-tabs>

    <el-tabs v-if="mainTab === 'lists'" v-model="listTab" type="card" @tab-change="load">
      <el-tab-pane v-for="t in listTabs" :key="t.key" :label="t.label" :name="t.key" />
    </el-tabs>

    <div class="toolbar" v-if="mainTab === 'scans'">
      <el-button type="primary" @click="doScan">发起扫描</el-button>
    </div>
    <div class="toolbar" v-if="mainTab === 'lists'">
      <el-input v-model="search" placeholder="实体名称" clearable style="width: 200px" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="entity_name" label="名称" min-width="200" v-if="mainTab === 'lists'" />
      <el-table-column prop="entity_type" label="类型" width="100" v-if="mainTab === 'lists'" />
      <el-table-column prop="list_type" label="名单" width="100" v-if="mainTab === 'lists'" />
      <el-table-column prop="country" label="国家/城市" min-width="120" v-if="mainTab === 'lists'" />
      <el-table-column prop="risk_level" label="风险" width="90" v-if="mainTab === 'lists'" />
      <el-table-column prop="scan_type" label="扫描类型" min-width="140" v-if="mainTab === 'scans'" />
      <el-table-column prop="status" label="状态" min-width="120" v-if="mainTab === 'scans' || mainTab === 'hits'" />
      <el-table-column prop="entity_name" label="命中主体" min-width="200" v-if="mainTab === 'hits'" />
      <el-table-column prop="hit_count" label="命中数" width="100" v-if="mainTab === 'scans'" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSanctionLists, getSanctionScans, createSanctionScan, getSanctionHits } from '@/api/compliance'

const mainTab = ref('lists')
const listTab = ref('UN_PERSON')
const listTabs = [
  { key: 'UN_PERSON', label: 'UN-人名', list_type: 'UN', entity_type: 'PERSON' },
  { key: 'UN_CITY', label: 'UN-城市', list_type: 'UN', entity_type: 'CITY' },
  { key: 'UN_COUNTRY', label: 'UN-国家', list_type: 'UN', entity_type: 'COUNTRY' },
  { key: 'OFAC_PERSON', label: 'OFAC-人名', list_type: 'OFAC', entity_type: 'PERSON' },
  { key: 'OFAC_CITY', label: 'OFAC-城市', list_type: 'OFAC', entity_type: 'CITY' },
  { key: 'OFAC_COUNTRY', label: 'OFAC-国家', list_type: 'OFAC', entity_type: 'COUNTRY' },
]
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const search = ref('')

function currentListFilter() {
  return listTabs.find((t) => t.key === listTab.value) || listTabs[0]
}

async function load() {
  loading.value = true
  try {
    if (mainTab.value === 'lists') {
      const f = currentListFilter()
      const data = await getSanctionLists({
        page: page.value,
        page_size: pageSize.value,
        list_type: f.list_type,
        entity_type: f.entity_type,
        search: search.value || undefined
      })
      rows.value = data.results || []
      total.value = data.count || 0
    } else if (mainTab.value === 'scans') {
      const data = await getSanctionScans({ page: page.value, page_size: pageSize.value })
      rows.value = data.results || []
      total.value = data.count || 0
    } else {
      const data = await getSanctionHits({ page: page.value, page_size: pageSize.value })
      rows.value = data.results || []
      total.value = data.count || 0
    }
  } finally {
    loading.value = false
  }
}
function onMainTab() {
  page.value = 1
  load()
}
function onPage(p) {
  page.value = p
  load()
}
async function doScan() {
  await createSanctionScan({ scan_type: 'FULL' })
  ElMessage.success('扫描已发起')
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
