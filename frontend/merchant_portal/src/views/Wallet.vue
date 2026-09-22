<template>
  <div>
    <h1 class="ptitle">{{ $t('wallet.title') }}</h1>
    <p class="psub">{{ $t('wallet.subtitle') }}</p>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      :title="$t('wallet.recordHint')"
      class="record-alert"
    />

    <div v-if="wallets.length" class="balance-grid" data-testid="wallet-balances">
      <div
        v-for="item in wallets"
        :key="item.currency"
        class="balance-card"
        :class="{ frozen: item.status === 'FROZEN' }"
      >
        <div class="balance-top">
          <span class="ccy">{{ item.currency }}</span>
          <el-tag :type="statusTagType(item.status)" size="small" effect="plain">
            {{ statusLabel(item.status) }}
          </el-tag>
        </div>
        <div class="balance-amount">{{ money(item.balance) }}</div>
        <div class="balance-meta">
          <span>{{ $t('wallet.available') }} {{ money(item.available) }}</span>
          <span v-if="Number(item.frozen) > 0">{{ $t('wallet.frozenAmt') }} {{ money(item.frozen) }}</span>
        </div>
      </div>
    </div>
    <div v-else class="page-card" data-testid="wallet-empty">
      <el-empty :description="$t('wallet.empty')" />
    </div>

    <div class="page-card">
      <div class="section-bar">
        <h2 class="section-heading">{{ $t('wallet.txTitle') }}</h2>
        <div class="toolbar inline">
          <el-select v-model="txFilter" clearable :placeholder="$t('wallet.txType')" style="width: 160px">
            <el-option :label="$t('wallet.typeTopUp')" value="TOP_UP" />
            <el-option :label="$t('wallet.typeWithdraw')" value="WITHDRAW" />
            <el-option :label="$t('wallet.typeTransferIn')" value="TRANSFER_IN" />
            <el-option :label="$t('wallet.typeTransferOut')" value="TRANSFER_OUT" />
            <el-option :label="$t('wallet.typeFreeze')" value="FREEZE" />
            <el-option :label="$t('wallet.typeUnfreeze')" value="UNFREEZE" />
          </el-select>
          <el-select v-model="txCurrency" clearable :placeholder="$t('common.currency')" style="width: 120px">
            <el-option v-for="w in wallets" :key="w.currency" :label="w.currency" :value="w.currency" />
          </el-select>
        </div>
      </div>

      <el-table v-if="filteredTxns.length" :data="filteredTxns" max-height="420">
        <el-table-column prop="id" :label="$t('wallet.txId')" min-width="130" />
        <el-table-column :label="$t('wallet.txType')" min-width="130">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="currency" :label="$t('common.currency')" width="100" />
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">
            <span :class="amountClass(row)">{{ signedAmount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('wallet.balanceAfter')" min-width="140">
          <template #default="{ row }">{{ money(row.balance_after) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'SUCCESS' ? 'success' : 'warning'" size="small" effect="plain">
              {{ row.status === 'SUCCESS' ? $t('wallet.statusSuccess') : $t('wallet.statusPending') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('wallet.time')" min-width="170">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="remark" :label="$t('wallet.remark')" min-width="160" show-overflow-tooltip />
      </el-table>
      <el-empty v-else data-testid="wallet-tx-empty" :description="$t('wallet.txEmpty')" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { WALLET_CREDIT_TYPES, useFundingStore } from '@/store/funding'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const funding = useFundingStore()
const { wallets, walletTxns } = storeToRefs(funding)

onMounted(() => funding.ensureExhibitionFunding(auth.user))

const txFilter = ref('')
const txCurrency = ref('')

const filteredTxns = computed(() => {
  return walletTxns.value.filter((row) => {
    if (txFilter.value && row.type !== txFilter.value) return false
    if (txCurrency.value && row.currency !== txCurrency.value) return false
    return true
  })
})

function statusTagType(status) {
  if (status === 'FROZEN') return 'warning'
  if (status === 'ACTIVE') return 'success'
  return 'info'
}

function statusLabel(status) {
  if (status === 'FROZEN') return t('wallet.statusFrozen')
  return t('wallet.statusActive')
}

function typeLabel(type) {
  const map = {
    TOP_UP: t('wallet.typeTopUp'),
    WITHDRAW: t('wallet.typeWithdraw'),
    TRANSFER_IN: t('wallet.typeTransferIn'),
    TRANSFER_OUT: t('wallet.typeTransferOut'),
    FREEZE: t('wallet.typeFreeze'),
    UNFREEZE: t('wallet.typeUnfreeze')
  }
  return map[type] || type
}

function signedAmount(row) {
  const prefix = WALLET_CREDIT_TYPES.has(row.type) ? '+' : '-'
  return `${prefix}${money(row.amount)}`
}

function amountClass(row) {
  return WALLET_CREDIT_TYPES.has(row.type) ? 'amt-in' : 'amt-out'
}
</script>

<style scoped>
.ptitle { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.record-alert { margin-bottom: 16px; }
.balance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.balance-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.balance-card.frozen { opacity: 0.85; }
.balance-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.ccy { font-weight: 700; font-size: 15px; color: #5c4033; }
.balance-amount {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  letter-spacing: -0.02em;
  margin-bottom: 8px;
}
.balance-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: #8c8c8c;
}
.page-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.toolbar.inline { margin: 0; }
.section-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.section-heading { margin: 0; font-size: 16px; font-weight: 600; }
.amt-in { color: #2f9e44; font-weight: 600; }
.amt-out { color: #c0392b; font-weight: 600; }
</style>
