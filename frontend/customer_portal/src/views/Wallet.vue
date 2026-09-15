<template>
  <div>
    <h1 class="ptitle">{{ $t('wallet.title') }}</h1>
    <p class="psub">{{ $t('wallet.subtitle') }}</p>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      :title="$t('wallet.demoHint')"
      class="demo-alert"
    />

    <div class="balance-grid">
      <div
        v-for="item in wallets"
        :key="item.currency"
        class="balance-card"
        :class="{ active: activeCurrency === item.currency, frozen: item.status === 'FROZEN' }"
        @click="activeCurrency = item.currency"
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

    <div class="page-card actions-card">
      <div class="toolbar">
        <el-button type="primary" :disabled="!canOperate" @click="openDialog('topup')">
          {{ $t('wallet.topUp') }}
        </el-button>
        <el-button :disabled="!canOperate" @click="openDialog('withdraw')">
          {{ $t('wallet.withdraw') }}
        </el-button>
        <el-button :disabled="!canOperate" @click="openDialog('transfer')">
          {{ $t('wallet.transfer') }}
        </el-button>
        <el-button
          v-if="activeWallet?.status !== 'FROZEN'"
          :disabled="!activeWallet"
          @click="freezeWallet"
        >
          {{ $t('wallet.freeze') }}
        </el-button>
        <el-button
          v-else
          type="success"
          plain
          :disabled="!activeWallet"
          @click="unfreezeWallet"
        >
          {{ $t('wallet.unfreeze') }}
        </el-button>
        <el-button @click="resetDemo">{{ $t('wallet.resetDemo') }}</el-button>
      </div>
      <p class="hint">{{ $t('wallet.activeHint', { ccy: activeCurrency || '—' }) }}</p>
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
      <el-empty v-else :description="$t('wallet.txEmpty')" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="440px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form :model="form" label-width="110px">
        <el-form-item :label="$t('common.currency')">
          <el-input :model-value="form.currency" disabled />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'transfer'" :label="$t('wallet.toCurrency')">
          <el-select v-model="form.toCurrency" style="width: 100%">
            <el-option
              v-for="w in transferTargets"
              :key="w.currency"
              :label="w.currency"
              :value="w.currency"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('common.amount')">
          <el-input v-model="form.amount" :placeholder="$t('wallet.amountPh')" />
        </el-form-item>
        <el-form-item :label="$t('wallet.remark')">
          <el-input v-model="form.remark" :placeholder="$t('wallet.remarkPh')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAction">
          {{ $t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { datetime, money } from '@/utils/format'

const { t } = useI18n()

const DEMO_WALLETS = [
  { currency: 'USD', balance: '12580.50', available: '12580.50', frozen: '0.00', status: 'ACTIVE' },
  { currency: 'EUR', balance: '4320.00', available: '3820.00', frozen: '500.00', status: 'ACTIVE' },
  { currency: 'KES', balance: '250000.00', available: '250000.00', frozen: '0.00', status: 'ACTIVE' },
  { currency: 'CNY', balance: '0.00', available: '0.00', frozen: '0.00', status: 'ACTIVE' }
]

function seedTxns() {
  const now = Date.now()
  return [
    {
      id: 'TXN-1006',
      type: 'TOP_UP',
      currency: 'USD',
      amount: '2000.00',
      balance_after: '12580.50',
      status: 'SUCCESS',
      remark: 'Bank transfer credit',
      created_at: new Date(now - 3600e3).toISOString()
    },
    {
      id: 'TXN-1005',
      type: 'TRANSFER_OUT',
      currency: 'EUR',
      amount: '500.00',
      balance_after: '4320.00',
      status: 'SUCCESS',
      remark: 'Hold for remittance',
      created_at: new Date(now - 86400e3).toISOString()
    },
    {
      id: 'TXN-1004',
      type: 'WITHDRAW',
      currency: 'KES',
      amount: '15000.00',
      balance_after: '250000.00',
      status: 'PENDING',
      remark: 'Payout to M-Pesa',
      created_at: new Date(now - 2 * 86400e3).toISOString()
    },
    {
      id: 'TXN-1003',
      type: 'TOP_UP',
      currency: 'KES',
      amount: '100000.00',
      balance_after: '265000.00',
      status: 'SUCCESS',
      remark: 'Agent cash deposit',
      created_at: new Date(now - 3 * 86400e3).toISOString()
    },
    {
      id: 'TXN-1002',
      type: 'TRANSFER_IN',
      currency: 'USD',
      amount: '800.00',
      balance_after: '10580.50',
      status: 'SUCCESS',
      remark: 'From EUR wallet',
      created_at: new Date(now - 5 * 86400e3).toISOString()
    },
    {
      id: 'TXN-1001',
      type: 'TOP_UP',
      currency: 'EUR',
      amount: '5000.00',
      balance_after: '4820.00',
      status: 'SUCCESS',
      remark: 'Initial funding',
      created_at: new Date(now - 7 * 86400e3).toISOString()
    }
  ]
}

const wallets = ref(structuredClone(DEMO_WALLETS))
const txns = ref(seedTxns())
const activeCurrency = ref('USD')
const txFilter = ref('')
const txCurrency = ref('')
const dialogVisible = ref(false)
const dialogMode = ref('topup')
const submitting = ref(false)
const form = reactive({ currency: '', toCurrency: '', amount: '', remark: '' })
let txnSeq = 1007

const activeWallet = computed(() => wallets.value.find((w) => w.currency === activeCurrency.value) || null)
const canOperate = computed(() => activeWallet.value && activeWallet.value.status === 'ACTIVE')
const transferTargets = computed(() =>
  wallets.value.filter((w) => w.currency !== form.currency && w.status === 'ACTIVE')
)
const dialogTitle = computed(() => {
  if (dialogMode.value === 'topup') return t('wallet.topUp')
  if (dialogMode.value === 'withdraw') return t('wallet.withdraw')
  return t('wallet.transfer')
})
const filteredTxns = computed(() => {
  return txns.value.filter((row) => {
    if (txFilter.value && row.type !== txFilter.value) return false
    if (txCurrency.value && row.currency !== txCurrency.value) return false
    return true
  })
})

function dec(v) {
  return Number(v || 0)
}

function fmt(n) {
  return (Math.round(n * 100) / 100).toFixed(2)
}

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

function isCredit(type) {
  return type === 'TOP_UP' || type === 'TRANSFER_IN' || type === 'UNFREEZE'
}

function signedAmount(row) {
  const prefix = isCredit(row.type) ? '+' : '-'
  return `${prefix}${money(row.amount)}`
}

function amountClass(row) {
  return isCredit(row.type) ? 'amt-in' : 'amt-out'
}

function pushTxn(partial) {
  const id = `TXN-${txnSeq++}`
  txns.value.unshift({
    id,
    status: 'SUCCESS',
    remark: '',
    created_at: new Date().toISOString(),
    ...partial
  })
}

function openDialog(mode) {
  if (!activeWallet.value) return
  dialogMode.value = mode
  form.currency = activeWallet.value.currency
  form.toCurrency = transferTargets.value[0]?.currency || ''
  form.amount = ''
  form.remark = ''
  dialogVisible.value = true
}

function resetForm() {
  form.currency = ''
  form.toCurrency = ''
  form.amount = ''
  form.remark = ''
}

function parseAmount() {
  const amount = Number(form.amount)
  if (!form.currency || !amount || amount <= 0) {
    ElMessage.warning(t('wallet.amountRequired'))
    return null
  }
  return amount
}

function findWallet(ccy) {
  return wallets.value.find((w) => w.currency === ccy)
}

async function submitAction() {
  const amount = parseAmount()
  if (amount == null) return

  const wallet = findWallet(form.currency)
  if (!wallet || wallet.status !== 'ACTIVE') {
    ElMessage.warning(t('wallet.notActive'))
    return
  }

  submitting.value = true
  try {
    await new Promise((r) => setTimeout(r, 350))

    if (dialogMode.value === 'topup') {
      wallet.balance = fmt(dec(wallet.balance) + amount)
      wallet.available = fmt(dec(wallet.available) + amount)
      pushTxn({
        type: 'TOP_UP',
        currency: wallet.currency,
        amount: fmt(amount),
        balance_after: wallet.balance,
        remark: form.remark || t('wallet.defaultTopUpRemark')
      })
      ElMessage.success(t('wallet.topUpOk'))
    } else if (dialogMode.value === 'withdraw') {
      if (dec(wallet.available) < amount) {
        ElMessage.warning(t('wallet.insufficient'))
        return
      }
      wallet.balance = fmt(dec(wallet.balance) - amount)
      wallet.available = fmt(dec(wallet.available) - amount)
      pushTxn({
        type: 'WITHDRAW',
        currency: wallet.currency,
        amount: fmt(amount),
        balance_after: wallet.balance,
        status: 'PENDING',
        remark: form.remark || t('wallet.defaultWithdrawRemark')
      })
      ElMessage.success(t('wallet.withdrawOk'))
    } else {
      if (!form.toCurrency) {
        ElMessage.warning(t('wallet.toCurrencyRequired'))
        return
      }
      if (dec(wallet.available) < amount) {
        ElMessage.warning(t('wallet.insufficient'))
        return
      }
      const target = findWallet(form.toCurrency)
      if (!target || target.status !== 'ACTIVE') {
        ElMessage.warning(t('wallet.targetNotActive'))
        return
      }
      wallet.balance = fmt(dec(wallet.balance) - amount)
      wallet.available = fmt(dec(wallet.available) - amount)
      target.balance = fmt(dec(target.balance) + amount)
      target.available = fmt(dec(target.available) + amount)
      pushTxn({
        type: 'TRANSFER_OUT',
        currency: wallet.currency,
        amount: fmt(amount),
        balance_after: wallet.balance,
        remark: form.remark || t('wallet.defaultTransferOut', { ccy: target.currency })
      })
      pushTxn({
        type: 'TRANSFER_IN',
        currency: target.currency,
        amount: fmt(amount),
        balance_after: target.balance,
        remark: form.remark || t('wallet.defaultTransferIn', { ccy: wallet.currency })
      })
      ElMessage.success(t('wallet.transferOk'))
    }
    dialogVisible.value = false
  } finally {
    submitting.value = false
  }
}

function freezeWallet() {
  const wallet = activeWallet.value
  if (!wallet || wallet.status === 'FROZEN') return
  const avail = dec(wallet.available)
  wallet.status = 'FROZEN'
  wallet.frozen = fmt(dec(wallet.frozen) + avail)
  wallet.available = '0.00'
  pushTxn({
    type: 'FREEZE',
    currency: wallet.currency,
    amount: fmt(avail),
    balance_after: wallet.balance,
    remark: t('wallet.freezeRemark')
  })
  ElMessage.success(t('wallet.freezeOk'))
}

function unfreezeWallet() {
  const wallet = activeWallet.value
  if (!wallet || wallet.status !== 'FROZEN') return
  const frozen = dec(wallet.frozen)
  wallet.status = 'ACTIVE'
  wallet.available = fmt(dec(wallet.available) + frozen)
  wallet.frozen = '0.00'
  pushTxn({
    type: 'UNFREEZE',
    currency: wallet.currency,
    amount: fmt(frozen),
    balance_after: wallet.balance,
    remark: t('wallet.unfreezeRemark')
  })
  ElMessage.success(t('wallet.unfreezeOk'))
}

function resetDemo() {
  wallets.value = structuredClone(DEMO_WALLETS)
  txns.value = seedTxns()
  txnSeq = 1007
  activeCurrency.value = 'USD'
  txFilter.value = ''
  txCurrency.value = ''
  ElMessage.success(t('wallet.resetOk'))
}
</script>

<style scoped>
.ptitle { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.demo-alert { margin-bottom: 16px; }
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
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.balance-card:hover { box-shadow: 0 2px 10px rgba(224, 112, 48, 0.12); }
.balance-card.active { border-color: var(--tech-orange, #f08040); }
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
.actions-card .toolbar { margin-bottom: 8px; }
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
.hint { margin: 0; color: #8c8c8c; font-size: 13px; }
.amt-in { color: #2f9e44; font-weight: 600; }
.amt-out { color: #c0392b; font-weight: 600; }
</style>
