<template>
  <div class="page-card">
    <div class="toolbar">
      <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <el-table v-loading="loading" :data="items" stripe border empty-text="暂无支付记录">
      <el-table-column prop="order_no" label="订单号" min-width="180" />
      <el-table-column prop="merchant_name" label="商户" min-width="140" />
      <el-table-column prop="amount" label="金额" width="120" />
      <el-table-column prop="pay_method" label="支付方式" width="120" />
      <el-table-column prop="order_status" label="订单状态" width="120" />
      <el-table-column prop="pay_time" label="支付时间" min-width="170">
        <template #default="{ row }">
          {{ formatTime(row.pay_time) }}
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top: 16px; display: flex; justify-content: flex-end">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadData"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getPaymentHistory } from '@/api/payments'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

async function loadData() {
  loading.value = true
  try {
    const res = await getPaymentHistory({ page: page.value, page_size: pageSize.value })
    items.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function onSizeChange() {
  page.value = 1
  loadData()
}

onMounted(loadData)
</script>
