<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="调拨单号" clearable style="width: 220px" @keyup.enter="reload" />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="transfer_no" label="调拨单号" min-width="200" />
      <el-table-column prop="from_account" label="出账账户" min-width="160" />
      <el-table-column prop="to_account" label="入账账户" min-width="160" />
      <el-table-column prop="amount" label="金额" min-width="120" />
      <el-table-column prop="status" label="状态" min-width="120" />
    </el-table>

    <el-pagination
      class="toolbar"
      background
      layout="total, prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="onPage"
    />
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getFundTransfers } from '@/api/accounts'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '' })

async function load() {
  loading.value = true
  try {
    const data = await getFundTransfers({ page: page.value, page_size: pageSize.value, search: filters.search || undefined })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}
function reload() {
  page.value = 1
  load()
}
function reset() {
  filters.search = ''
  reload()
}
function onPage(p) {
  page.value = p
  load()
}
onMounted(load)
</script>
