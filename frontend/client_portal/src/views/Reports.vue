<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-select v-model="activeReport" placeholder="报表类型" style="width: 200px" @change="query">
        <el-option label="汇款报表" value="remittance" />
        <el-option label="商户日报" value="merchant-daily" />
        <el-option label="通道费报表" value="channel-fee" />
        <el-option label="平台汇总" value="platform-summary" />
        <el-option label="结算批次报表" value="settle-batches" />
        <el-option label="结算明细报表" value="settle-details" />
        <el-option label="分润记录" value="fee-shares" />
      </el-select>
      <el-date-picker v-model="filters.range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width: 260px" />
      <el-input v-model="filters.merchant" placeholder="客户名称" clearable style="width: 180px" />
      <el-button type="primary" @click="query">查询</el-button>
      <el-button type="success" @click="exportExcel">导出</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column type="index" label="#" width="60" />
      <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label" :min-width="col.width || 140" />
    </el-table>

    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { queryReport, exportReport } from '@/api/report'
import request from '@/api/request'

const activeReport = ref('remittance')
const rows = ref([])
const columns = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ range: [], merchant: '' })

const defaultColumns = [
  { prop: 'key', label: '标识', width: 180 },
  { prop: 'count', label: '笔数', width: 100 },
  { prop: 'amount', label: '金额', width: 140 },
  { prop: 'currency', label: '币种', width: 90 }
]

function queryParams() {
  const [date_from, date_to] = filters.range || []
  return {
    page: page.value,
    page_size: pageSize.value,
    date_from: date_from || undefined,
    date_to: date_to || undefined,
    date: date_from || undefined,
    merchant_name: filters.merchant || undefined,
    search: filters.merchant || undefined
  }
}

async function load() {
  loading.value = true
  try {
    if (activeReport.value === 'fee-shares') {
      const data = await request.get('/v1/admin/fee-shares/', { params: queryParams() })
      rows.value = data.results || []
      total.value = data.count || 0
      columns.value = [
        { prop: 'order_no', label: '订单号', width: 180 },
        { prop: 'agent_name', label: '代理', width: 120 },
        { prop: 'agent_fee', label: '代理分润', width: 120 },
        { prop: 'channel_fee', label: '银行手续费', width: 120 },
        { prop: 'platform_fee', label: '平台收入', width: 120 },
        { prop: 'total_fee', label: '手续费合计', width: 120 }
      ]
      return
    }
    const data = await queryReport(activeReport.value, queryParams())
    rows.value = data.results || []
    total.value = data.count || 0
    columns.value = (data.columns && data.columns.length) ? data.columns : defaultColumns
  } finally {
    loading.value = false
  }
}
function query() {
  page.value = 1
  load()
}
function exportExcel() {
  if (activeReport.value === 'fee-shares') {
    ElMessage.info('分润请在结算分润页导出')
    return
  }
  exportReport(activeReport.value, queryParams())
    .then(() => ElMessage.success('已触发导出'))
    .catch(() => {})
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
