<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.customersTitle') }}</h1>
    <p class="psub">{{ $t('agent.customersSub') }}</p>
    <div class="page-card">
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="merchant_no" :label="$t('agent.customerNo')" min-width="140" />
        <el-table-column prop="merchant_name" :label="$t('agent.customerName')" min-width="180" />
        <el-table-column prop="status" :label="$t('common.status')" width="120" />
        <el-table-column :label="$t('agent.accountBalance')" min-width="220">
          <template #default="{ row }">{{ formatBalances(row.balances) }}</template>
        </el-table-column>
        <el-table-column prop="commission_rate" :label="$t('agent.commission')" min-width="130" />
        <el-table-column prop="effective_from" :label="$t('agent.effectiveFrom')" min-width="130" />
        <el-table-column :label="$t('agent.effectiveTo')" min-width="130">
          <template #default="{ row }">{{ row.effective_to || '—' }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goAccount(row)">
              {{ $t('agent.accountView') }}
            </el-button>
            <el-button
              link
              type="primary"
              :disabled="!row.remittance_eligibility?.eligible"
              @click="goRemit(row)"
            >
              {{ $t('agent.remitAction') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.emptyCustomers')" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { getAgentMerchants } from '@/api/agent'
import { money } from '@/utils/format'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const rows = ref([])

function formatBalances(balances) {
  if (!balances?.length) return '—'
  return balances
    .map((row) => `${row.currency} ${money(row.available_balance)}`)
    .join(' · ')
}

function goRemit(row) {
  router.push({ name: 'agent-remittance', query: { merchant_id: row.id } })
}

function goAccount(row) {
  router.push({ name: 'agent-account', query: { merchant_id: row.id } })
}

onMounted(async () => {
  if (auth.onboardingStatus !== 'approved') return
  loading.value = true
  try {
    const data = await getAgentMerchants()
    rows.value = data.items || data.results || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
</style>
