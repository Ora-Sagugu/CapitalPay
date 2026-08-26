<template>
  <el-card class="page-card" shadow="never">
    <div class="toolbar">
      <el-input v-model="filters.search" placeholder="账户号 / 银行" clearable style="width: 220px" @keyup.enter="reload" />
      <el-select v-model="filters.currency" placeholder="币种" clearable style="width: 120px" @change="reload">
        <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="account_no" label="账户号" min-width="160" />
      <el-table-column prop="bank_name" label="银行" min-width="140" />
      <el-table-column prop="currency" label="币种" width="90" />
      <el-table-column prop="balance" label="余额" min-width="120" />
      <el-table-column prop="max_single_amount" label="单笔限额" min-width="110" />
      <el-table-column prop="daily_limit" label="日限额" min-width="110" />
      <el-table-column prop="is_active" label="启用" width="80">
        <template #default="{ row }">{{ row.is_active === false ? '否' : '是' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="success" @click="recharge(row)">充值</el-button>
          <el-button link @click="showTx(row)">交易历史</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="toolbar" background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="onPage" />

    <el-dialog v-model="txVisible" title="交易历史" width="720px">
      <el-table :data="txRows" border stripe max-height="420">
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="ref_no" label="单号" min-width="160" />
        <el-table-column prop="created_at" label="时间" min-width="160" />
      </el-table>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getNostroAccounts, rechargeNostro, getNostroTransactions, getVirtualAccounts } from '@/api/accounts'

const currencies = ['USD', 'EUR', 'GBP', 'CNY', 'JPY', 'HKD']
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ search: '', currency: '' })
const txVisible = ref(false)
const txRows = ref([])

async function load() {
  loading.value = true
  try {
    // 优先多币种 Nostro；若无数据再展示 VA
    const data = await getNostroAccounts({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      currency: filters.currency || undefined
    })
    let list = data.results || []
    if (!list.length && page.value === 1) {
      const va = await getVirtualAccounts({ page: 1, page_size: pageSize.value, search: filters.search || undefined })
      list = (va.results || []).map((v) => ({
        id: v.id,
        account_no: v.va_number || v.account_no,
        bank_name: v.bank_name,
        currency: v.currency,
        balance: v.balance,
        is_active: v.status !== 'INACTIVE',
        _isVa: true
      }))
      total.value = va.count || 0
    } else {
      total.value = data.count || 0
    }
    rows.value = list
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
  load()
}
async function recharge(row) {
  if (row._isVa) {
    ElMessage.info('请在 Nostro 账户上充值')
    return
  }
  const { value } = await ElMessageBox.prompt('充值金额', '账户充值', { inputPattern: /.+/ })
  await rechargeNostro(row.id, { amount: value })
  ElMessage.success('充值成功')
  load()
}
async function showTx(row) {
  if (row._isVa) {
    ElMessage.info('VA 交易请查看母账户流水')
    return
  }
  const data = await getNostroTransactions(row.id)
  txRows.value = data.transactions || []
  txVisible.value = true
}
onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 16px; display: flex; gap: 8px; }
</style>
