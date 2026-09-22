<template>
  <div>
    <div class="page-head">
      <h1 class="ptitle">{{ $t('accounts.title') }}</h1>
    </div>

    <div class="kpi-grid">
      <div class="page-card kpi-card" data-testid="spendable">
        <h2 class="kpi-label">{{ $t('accounts.spendable') }}</h2>
        <el-table v-if="spendable.length" :data="spendable" size="small">
          <el-table-column prop="currency" :label="$t('common.currency')" min-width="90" />
          <el-table-column :label="$t('accounts.total')" min-width="120">
            <template #default="{ row }">{{ money(row.amount) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else :description="$t('accounts.emptyBalances')" />
      </div>
    </div>

    <div class="rail-grid">
      <div
        v-for="rail in rails"
        :key="rail.id"
        class="page-card rail-card"
        :data-testid="`rail-${rail.id}`"
      >
        <div class="rail-top">
          <h2 class="section-heading">{{ rail.title }}</h2>
          <router-link :to="{ name: rail.route }">{{ $t('common.view') }}</router-link>
        </div>
        <p class="rail-metric">{{ rail.metric }}</p>
      </div>
    </div>

    <div class="page-card">
      <h2 class="section-heading">{{ $t('accounts.activity') }}</h2>
      <el-table v-if="activity.length" :data="activity" v-loading="ledgerLoading">
        <el-table-column :label="$t('accounts.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('accounts.rail')" min-width="110">
          <template #default="{ row }">{{ railLabel(row.rail) }}</template>
        </el-table-column>
        <el-table-column prop="currency" :label="$t('common.currency')" min-width="90" />
        <el-table-column :label="$t('common.amount')" min-width="130">
          <template #default="{ row }">
            <span :class="row.entry_type === 'DEBIT' ? 'amt-out' : 'amt-in'">
              {{ signedAmount(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" :label="$t('wallet.remark')" min-width="200" show-overflow-tooltip />
      </el-table>
      <el-empty v-else-if="!ledgerLoading" :description="$t('accounts.emptyLedger')" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ENABLE_CARDS } from '@/config/features'
import { useAuthStore } from '@/store/auth'
import { useFundingStore } from '@/store/funding'
import { getAccountLedger, listBoundAccounts } from '@/api/payments'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const funding = useFundingStore()

const ledgerLoading = ref(false)
const bankBalances = ref([])
const bankLedger = ref([])

const spendable = computed(() => funding.spendableRows(bankBalances.value))
const activity = computed(() => funding.hubActivity({ bankLedger: bankLedger.value }))

const rails = computed(() => {
  const items = [
    {
      id: 'bank',
      title: t('accounts.railCapitalPay'),
      route: 'bank',
      metric: formatPrimary(bankBalances.value, 'balance')
    },
    {
      id: 'wallet',
      title: t('menu.wallet'),
      route: 'wallet',
      metric: formatPrimary(funding.walletAvailableRows, 'amount')
    }
  ]
  if (ENABLE_CARDS) {
    items.push({
      id: 'cards',
      title: t('menu.cards'),
      route: 'cards',
      metric: formatPrimary(funding.cardAvailableRows, 'amount')
    })
  }
  return items
})

function formatPrimary(rows, key) {
  if (!rows || !rows.length) return money(0)
  const usd = rows.find((row) => row.currency === 'USD')
  const row = usd || rows[0]
  return `${row.currency} ${money(row[key])}`
}

function railLabel(rail) {
  if (rail === 'BANK') return t('accounts.railCapitalPay')
  if (rail === 'WALLET') return t('menu.wallet')
  return t('menu.cards')
}

function signedAmount(row) {
  const prefix = row.entry_type === 'DEBIT' ? '-' : '+'
  return `${prefix}${money(row.amount)}`
}

async function loadBank() {
  if (auth.onboardingStatus !== 'approved') return
  ledgerLoading.value = true
  try {
    const overview = await listBoundAccounts()
    bankBalances.value = (overview.balances || []).map((row) => ({
      currency: (row.currency || '').toUpperCase(),
      balance: row.balance || '0.00'
    }))
    const data = await getAccountLedger({ page: 1, page_size: 20 })
    bankLedger.value = data.items || []
  } finally {
    ledgerLoading.value = false
  }
}

onMounted(() => {
  funding.ensureExhibitionFunding(auth.user)
  loadBank()
})
</script>

<style scoped>
.page-head { margin-bottom: 16px; }
.ptitle { margin: 0; font-size: 22px; font-weight: 700; color: #303133; }
.page-card { background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.kpi-grid, .rail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-bottom: 4px;
}
.kpi-label, .section-heading { margin: 0 0 8px; font-size: 16px; font-weight: 600; }
.rail-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.rail-top .section-heading { margin: 0; }
.rail-top a { color: var(--tech-orange-dark, #e07030); font-size: 13px; font-weight: 600; }
.rail-metric { margin: 0; font-size: 22px; font-weight: 700; }
.amt-in { color: #67c23a; }
.amt-out { color: #f56c6c; }
</style>
