<template>
  <div>
    <h1 class="ptitle">{{ $t('cards.title') }}</h1>
    <p class="psub">{{ $t('cards.subtitle') }}</p>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      :title="$t('cards.recordHint')"
      class="record-alert"
    />

    <div v-if="cardInstruments.length" class="instrument-row" data-testid="card-instruments">
      <span class="instrument-label">{{ $t('cards.instruments') }}</span>
      <el-tag
        v-for="item in cardInstruments"
        :key="item.id"
        size="small"
        effect="plain"
      >
        {{ maskCard(item) }}
      </el-tag>
    </div>

    <div v-if="cardBalances.length" class="balance-grid" data-testid="card-balances">
      <div
        v-for="item in cardBalances"
        :key="item.currency"
        class="balance-card"
        :class="{ frozen: item.status === 'FROZEN' }"
      >
        <div class="balance-top">
          <span class="ccy">{{ item.currency }}</span>
          <el-tag :type="statusTagType(item.status)" size="small" effect="plain">
            {{ typeLabel(item.status) }}
          </el-tag>
        </div>
        <div class="balance-amount">{{ money(item.ledger) }}</div>
        <div class="balance-meta">
          <span>{{ $t('cards.available') }} {{ money(item.available) }}</span>
          <span v-if="Number(item.pending) > 0">{{ $t('cards.pending') }} {{ money(item.pending) }}</span>
          <span v-if="Number(item.reserved) > 0">{{ $t('cards.reserved') }} {{ money(item.reserved) }}</span>
          <span v-if="Number(item.dispute_hold) > 0">{{ $t('cards.disputeHold') }} {{ money(item.dispute_hold) }}</span>
        </div>
      </div>
    </div>
    <div v-else class="page-card" data-testid="cards-empty">
      <el-empty :description="$t('cards.empty')" />
    </div>

    <div v-if="cardBalances.length" class="kpi-grid" data-testid="card-kpis">
      <div class="page-card kpi-card">
        <div class="kpi-label">{{ $t('cards.kpiOpenCheckouts') }}</div>
        <div class="kpi-value">{{ summary.openCheckouts }}</div>
      </div>
      <div class="page-card kpi-card">
        <div class="kpi-label">{{ $t('cards.kpiOpenRefunds') }}</div>
        <div class="kpi-value">{{ summary.openRefunds }}</div>
      </div>
      <div class="page-card kpi-card">
        <div class="kpi-label">{{ $t('cards.kpiOpenChargebacks') }}</div>
        <div class="kpi-value">{{ summary.openChargebacks }}</div>
      </div>
    </div>

    <div class="page-card">
      <div class="section-bar">
        <h2 class="section-heading">{{ $t('cards.txTitle') }}</h2>
        <div class="toolbar inline">
          <el-select v-model="txFilter" clearable :placeholder="$t('cards.txType')" style="width: 180px">
            <el-option :label="$t('cards.families.CHECKOUT')" value="CHECKOUT" />
            <el-option :label="$t('cards.families.REFUND')" value="REFUND" />
            <el-option :label="$t('cards.families.CHARGEBACK')" value="CHARGEBACK" />
          </el-select>
          <el-select v-model="txCurrency" clearable :placeholder="$t('common.currency')" style="width: 120px">
            <el-option v-for="c in cardBalances" :key="c.currency" :label="c.currency" :value="c.currency" />
          </el-select>
        </div>
      </div>

      <el-table
        v-if="filteredEvents.length"
        :data="filteredEvents"
        max-height="420"
        data-testid="card-events"
        @row-click="openTimeline"
      >
        <el-table-column :label="$t('cards.orderNo')" min-width="170">
          <template #default="{ row }">{{ orderNo(row) }}</template>
        </el-table-column>
        <el-table-column :label="$t('cards.txType')" min-width="160">
          <template #default="{ row }">{{ familyLabel(row.family, row) }}</template>
        </el-table-column>
        <el-table-column :label="$t('cards.card')" min-width="120">
          <template #default="{ row }">{{ maskCard(row) || '—' }}</template>
        </el-table-column>
        <el-table-column prop="currency" :label="$t('common.currency')" width="90" />
        <el-table-column :label="$t('common.amount')" min-width="130">
          <template #default="{ row }">
            <span :class="amountClass(row)">{{ signedAmount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" min-width="140">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
              {{ typeLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('cards.time')" min-width="170">
          <template #default="{ row }">{{ datetime(row.occurred_at) }}</template>
        </el-table-column>
        <el-table-column prop="remark" :label="$t('wallet.remark')" min-width="180" show-overflow-tooltip />
      </el-table>
      <el-empty v-else data-testid="card-tx-empty" :description="$t('cards.txEmpty')" />
    </div>

    <el-drawer
      v-model="drawerOpen"
      :title="$t('cards.timelineTitle')"
      size="420px"
      data-testid="card-timeline"
    >
      <p v-if="activePaymentId" class="drawer-ref">{{ activePaymentId }}</p>
      <p v-if="flowSteps.length" class="drawer-hint" data-testid="flow-hint">
        {{ flowHint }}
      </p>
      <el-timeline v-if="flowSteps.length" data-testid="payment-flow">
        <el-timeline-item
          v-for="(item, idx) in flowSteps"
          :key="item.key"
          :timestamp="datetime(item.event.occurred_at)"
          :type="flowItemType(item)"
          :hollow="false"
          placement="top"
        >
          <div class="tl-step">{{ $t('cards.flowStep', { n: idx + 1 }) }}</div>
          <div class="tl-type">{{ typeLabel(item.type) }}</div>
          <div class="tl-meta">
            {{ item.event.currency }} {{ signedAmount(item.event) }}
            <span v-if="item.event.raw_type && item.event.raw_type !== item.type"> · {{ item.event.raw_type }}</span>
          </div>
          <div v-if="item.event.reason_code" class="tl-reason">{{ $t('cards.reasonCode') }} {{ item.event.reason_code }}</div>
          <div class="tl-remark">{{ item.event.remark }}</div>
          <div v-if="item.isLast" class="tl-stop" data-testid="flow-stop">
            {{ item.isTerminal ? $t('cards.flowEnded') : $t('cards.flowStopped') }}
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else :description="$t('cards.timelineEmpty')" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { useFundingStore } from '@/store/funding'
import {
  CARD_EVENT_TYPE,
  CARD_FAMILY,
  PAYMENT_CHARGEBACK_PATH,
  cardEventSummary,
  eventDirection,
  eventAmount,
  maskCard,
  paymentFlowTimeline,
  statusTagType
} from '@/data/cardPlatform'
import { datetime, money } from '@/utils/format'

const { t, te } = useI18n()
const auth = useAuthStore()
const funding = useFundingStore()
const { cardBalances, cardEvents, cardInstruments } = storeToRefs(funding)

onMounted(() => funding.ensureExhibitionFunding(auth.user))

const txFilter = ref('')
const txCurrency = ref('')
const drawerOpen = ref(false)
const activePaymentId = ref('')
const activeDisputeId = ref('')
const activeUntilType = ref('')

const summary = computed(() => cardEventSummary(cardEvents.value))

const ACTIVITY_FAMILIES = new Set([
  CARD_FAMILY.CHECKOUT,
  CARD_FAMILY.REFUND,
  CARD_FAMILY.CHARGEBACK
])

const filteredEvents = computed(() => {
  return cardEvents.value.filter((row) => {
    if (!ACTIVITY_FAMILIES.has(row.family)) return false
    if (txFilter.value && row.family !== txFilter.value) return false
    if (txCurrency.value && row.currency !== txCurrency.value) return false
    return true
  })
})

const flowSteps = computed(() => paymentFlowTimeline(cardEvents.value, activePaymentId.value, {
  disputeId: activeDisputeId.value,
  untilType: activeUntilType.value
}))

const flowHint = computed(() => {
  const last = flowSteps.value[flowSteps.value.length - 1]
  if (!last) return ''
  if (last.isTerminal) return t('cards.flowHintEnded', { step: typeLabel(last.type) })
  return t('cards.flowHintStopped', { step: typeLabel(last.type) })
})

function familyLabel(family, row) {
  const key = `cards.families.${family}`
  const base = te(key) ? t(key) : family
  if (family === 'REFUND' && row?.refund_kind) {
    const kindKey = `cards.refundKinds.${row.refund_kind}`
    if (te(kindKey)) return t('cards.refundKindFamily', { kind: t(kindKey) })
  }
  return base
}

function typeLabel(type) {
  if (!type) return '—'
  const key = `cards.types.${type}`
  return te(key) ? t(key) : type
}

function orderNo(row) {
  return row.payment_id || row.object_id || row.id || '—'
}

function signedAmount(row) {
  const direction = eventDirection(row)
  const amount = money(eventAmount(row))
  if (!direction) return amount
  return `${direction === 'CREDIT' ? '+' : '-'}${amount}`
}

function amountClass(row) {
  const direction = eventDirection(row)
  if (direction === 'CREDIT') return 'amt-in'
  if (direction === 'DEBIT') return 'amt-out'
  return 'amt-neutral'
}

function flowItemType(item) {
  if (item.type === CARD_EVENT_TYPE.ARBITRATION) return item.isLast ? 'warning' : 'primary'
  if (item.type === CARD_EVENT_TYPE.PRESENTMENT) return 'info'
  if (item.isLast) return 'warning'
  return 'primary'
}

function openTimeline(row) {
  activePaymentId.value = row.payment_id || ''
  activeDisputeId.value = row.dispute_id || ''
  activeUntilType.value = PAYMENT_CHARGEBACK_PATH.includes(row.type) ? row.type : ''
  drawerOpen.value = true
}
</script>

<style scoped>
.ptitle { margin: 0 0 6px; font-size: 22px; font-weight: 700; color: #303133; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.record-alert { margin-bottom: 16px; }
.instrument-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.instrument-label { font-size: 13px; color: #8c8c8c; }
.balance-grid, .kpi-grid {
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
.kpi-card { margin-bottom: 0; }
.kpi-label { font-size: 13px; color: #8c8c8c; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; color: #303133; }
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
.amt-neutral { color: #606266; }
.drawer-ref { margin: 0 0 8px; font-weight: 600; color: #303133; }
.drawer-hint { margin: 0 0 16px; font-size: 13px; color: #8c8c8c; }
.tl-step { font-size: 11px; color: #a8abb2; margin-bottom: 2px; }
.tl-type { font-weight: 600; }
.tl-meta, .tl-reason, .tl-remark { font-size: 12px; color: #8c8c8c; margin-top: 2px; }
.tl-stop { margin-top: 8px; font-size: 12px; font-weight: 600; color: #e6a23c; }
</style>
