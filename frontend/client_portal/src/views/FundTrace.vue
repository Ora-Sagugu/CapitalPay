<template>
  <el-card class="page-card" shadow="never">
    <template #header><span class="card-title">资金追踪</span></template>
    <div class="toolbar">
      <el-input v-model="q.order_no" placeholder="平台订单号 RMT…" clearable style="width: 180px" />
      <el-input v-model="q.merchant_order_no" placeholder="商户订单号" clearable style="width: 160px" />
      <el-input v-model="q.prn" placeholder="PRN" clearable style="width: 140px" />
      <el-input v-model="q.beneficiary_name" placeholder="收款人姓名" clearable style="width: 140px" />
      <el-input v-model="q.remitter_name" placeholder="汇款方姓名" clearable style="width: 140px" />
      <el-button type="primary" :loading="loading" @click="search">查询</el-button>
    </div>

    <el-table v-if="pendingOrders.length" :data="pendingOrders" border stripe style="margin-bottom: 16px" @row-click="pickOrder">
      <el-table-column prop="order_no" label="订单号" />
      <el-table-column prop="beneficiary_name" label="收款人" />
      <el-table-column prop="amount" label="金额" />
      <el-table-column prop="status" label="状态" />
    </el-table>

    <div v-if="trace">
      <el-descriptions :column="3" border style="margin-bottom: 20px">
        <el-descriptions-item label="订单号">{{ trace.order_no }}</el-descriptions-item>
        <el-descriptions-item label="PRN">{{ trace.prn }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ trace.status }}</el-descriptions-item>
        <el-descriptions-item label="汇款方">{{ trace.remitter_name }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ trace.amount }} {{ trace.from_currency }}→{{ trace.to_currency }}</el-descriptions-item>
        <el-descriptions-item label="收款人">{{ trace.beneficiary_name }}</el-descriptions-item>
      </el-descriptions>

      <el-steps :active="stepActive" finish-status="success" align-center>
        <el-step v-for="s in steps" :key="s.key" :title="s.title" :description="s.desc" />
      </el-steps>

      <el-row :gutter="16" style="margin-top: 24px">
        <el-col :span="12" v-if="trace.virtual_account">
          <el-card shadow="never"><template #header>收款 VA</template>
            <div>账号：{{ trace.virtual_account.account_no }}</div>
            <div>银行：{{ trace.virtual_account.bank_name }}</div>
            <div>余额：{{ trace.virtual_account.balance }} {{ trace.virtual_account.currency }}</div>
          </el-card>
        </el-col>
        <el-col :span="12" v-if="trace.nostro_account">
          <el-card shadow="never"><template #header>Nostro</template>
            <div>账号：{{ trace.nostro_account.account_no }}</div>
            <div>银行：{{ trace.nostro_account.bank_name }}</div>
            <div>余额：{{ trace.nostro_account.balance }} {{ trace.nostro_account.currency }}</div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { traceFund } from '@/api/orders'

const loading = ref(false)
const trace = ref(null)
const pendingOrders = ref([])
const q = reactive({
  order_no: '', merchant_order_no: '', prn: '', beneficiary_name: '', remitter_name: ''
})

const steps = [
  { key: 'created', title: '创建', desc: '订单创建' },
  { key: 'review', title: '复核', desc: '运营审核' },
  { key: 'collect', title: '收款', desc: '资金入账' },
  { key: 'route', title: '路由', desc: '通道选择' },
  { key: 'clear', title: '清算', desc: '清算处理' },
  { key: 'credit', title: '入账', desc: '完成入账' },
]

const stepActive = computed(() => {
  if (!trace.value) return 0
  const idx = steps.findIndex((s) => s.key === trace.value.current_step)
  return idx < 0 ? 0 : idx + 1
})

async function search() {
  const params = Object.fromEntries(Object.entries(q).filter(([, v]) => v))
  if (!Object.keys(params).length) {
    ElMessage.warning('请至少填写一个查询条件')
    return
  }
  loading.value = true
  pendingOrders.value = []
  trace.value = null
  try {
    const data = await traceFund(params)
    if (data.pending_orders) {
      pendingOrders.value = data.pending_orders
      ElMessage.info('命中多笔，请点击选择')
    } else {
      trace.value = data
    }
  } finally {
    loading.value = false
  }
}
async function pickOrder(row) {
  const data = await traceFund({ order_no: row.order_no })
  pendingOrders.value = []
  trace.value = data
}
</script>

<style scoped>
.card-title { font-weight: 600; }
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
</style>
