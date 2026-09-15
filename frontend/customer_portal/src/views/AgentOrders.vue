<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.ordersTitle') }}</h1>
    <p class="psub">{{ $t('agent.ordersSub') }}</p>

    <el-alert
      v-if="auth.onboardingStatus !== 'approved'"
      :title="$t('agent.needOnboarding')"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <div class="page-card">
      <div class="toolbar">
        <el-input
          v-model="filters.search"
          :placeholder="$t('agent.ordersSearch')"
          clearable
          style="width: 260px"
          @keyup.enter="reload"
        />
        <el-select v-model="filters.stage" style="width: 200px" @change="reload">
          <el-option :label="$t('agent.ordersAll')" value="all" />
          <el-option :label="$t('agent.ordersNeedsReview')" value="needs_review" />
          <el-option :label="$t('agent.ordersAwaitingPayout')" value="awaiting_payout" />
          <el-option :label="$t('agent.ordersAgreed')" value="agreed" />
          <el-option :label="$t('agent.ordersRejected')" value="rejected" />
        </el-select>
        <el-button @click="reload">{{ $t('common.refresh') }}</el-button>
        <span class="kpi">{{ $t('agent.ordersAllKpi') }} {{ stats.total ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.ordersPendingKpi') }} {{ stats.pending ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.ordersAwaitingPayoutKpi') }} {{ stats.awaiting_payout ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.ordersAgreed') }} {{ stats.agreed ?? 0 }}</span>
        <span class="kpi">{{ $t('agent.ordersRejected') }} {{ stats.rejected ?? 0 }}</span>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="order_no" :label="$t('orders.orderNo')" min-width="170" />
        <el-table-column prop="merchant_name" :label="$t('agent.ordersCustomer')" min-width="150" />
        <el-table-column :label="$t('common.amount')" min-width="150">
          <template #default="{ row }">
            {{ money(row.amount) }}
            <span v-if="row.from_currency || row.to_currency" class="ccy-pair">
              {{ row.from_currency || '—' }}/{{ row.to_currency || '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="beneficiary_name" :label="$t('agent.ordersBeneficiary')" min-width="140" />
        <el-table-column :label="$t('common.status')" min-width="160">
          <template #default="{ row }">
            <el-tag :type="ORDER_STATUS_TYPE[row.status] || 'info'" size="small">
              {{ statusLabel(ORDER_STATUS, row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('orders.createdAt')" min-width="160">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.actions')" min-width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">{{ $t('agent.ordersView') }}</el-button>
            <el-button
              v-if="row.status === 'PENDING_AGENT_REVIEW'"
              link
              type="success"
              @click="reviewInstruction(row, 'agree')"
            >{{ $t('agent.ordersAgree') }}</el-button>
            <el-button
              v-if="row.status === 'PENDING_AGENT_REVIEW'"
              link
              type="danger"
              @click="reviewInstruction(row, 'reject')"
            >{{ $t('agent.ordersReject') }}</el-button>
            <el-button
              v-if="canRequestPayout(row)"
              link
              type="warning"
              @click="requestPayout(row)"
            >{{ $t('agent.ordersRequestPayout') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" :description="$t('agent.ordersEmpty')" />
      <el-pagination
        v-if="total > pageSize"
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="640px">
      <div v-loading="detailLoading">
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="$t('orders.orderNo')">{{ dash(detail.order_no) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('agent.ordersCustomer')">{{ dash(detail.merchant_name) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('common.status')">
            <el-tag :type="ORDER_STATUS_TYPE[detail.status] || 'info'" size="small">
              {{ statusLabel(ORDER_STATUS, detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('common.amount')">
            {{ money(detail.amount) }} {{ detail.from_currency || detail.currency || '' }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('orders.fee')">
            {{ money(detail.fee_amount) }} {{ detail.fee_currency || '' }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('orders.chargeBearer')">
            {{ FEE_BEARING[detail.fee_bearing] || detail.fee_bearing || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('orders.settleAmount')">
            {{ money(detail.settle_amount) }} {{ detail.to_currency || '' }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('agent.ordersBeneficiary')">{{ dash(detail.beneficiary_name) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('orders.beneficiaryBank')">{{ dash(detail.beneficiary_bank) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('orders.beneficiaryAccount')">{{ dash(detail.beneficiary_account) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('orders.beneficiarySwift')">{{ dash(detail.beneficiary_swift) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('orders.beneficiaryAddress')">{{ dash(detail.beneficiary_address) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('agent.ordersPurpose')">{{ dash(detail.remittance_purpose) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('agent.ordersPayoutRequest')">
            {{ payoutRequestLabel(detail) }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="detail.status === 'PENDING_AGENT_REVIEW'" class="drawer-actions">
          <el-button type="success" @click="reviewInstruction(detail, 'agree')">{{ $t('agent.ordersAgree') }}</el-button>
          <el-button type="danger" @click="reviewInstruction(detail, 'reject')">{{ $t('agent.ordersReject') }}</el-button>
        </div>
        <div v-else-if="canRequestPayout(detail)" class="drawer-actions">
          <el-button type="warning" @click="requestPayout(detail)">{{ $t('agent.ordersRequestPayout') }}</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { getAgentOrders, getAgentOrderDetail, reviewAgentOrder, requestAgentPayout } from '@/api/agent'
import { datetime, money, ORDER_STATUS, ORDER_STATUS_TYPE, FEE_BEARING, statusLabel } from '@/utils/format'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ search: '', stage: 'all' })
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})

const detailTitle = computed(() => {
  const no = detail.value?.order_no || ''
  return no ? `${t('agent.ordersDetailTitle')} — ${no}` : t('agent.ordersDetailTitle')
})

function dash(value) {
  return value || '—'
}

function canRequestPayout(row) {
  return row?.status === 'PAY_RECEIVED' && row?.agent_payout_request_status === 'pending'
}

function payoutRequestLabel(row) {
  const status = row?.agent_payout_request_status
  if (status === 'pending') return t('agent.ordersPayoutPending')
  if (status === 'requested') return t('agent.ordersPayoutRequested')
  return '—'
}

function patchRow(orderNo, patch) {
  const idx = rows.value.findIndex((r) => r.order_no === orderNo)
  if (idx !== -1) Object.assign(rows.value[idx], patch)
}

async function load() {
  if (auth.onboardingStatus !== 'approved') {
    rows.value = []
    stats.value = {}
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await getAgentOrders({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      stage: filters.stage || 'all'
    })
    rows.value = data.items || data.results || []
    total.value = data.total || data.count || 0
    stats.value = data.stats || {}
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

async function openDetail(row) {
  detail.value = { ...row }
  detailVisible.value = true
  detailLoading.value = true
  try {
    const data = await getAgentOrderDetail(row.order_no)
    detail.value = data
  } finally {
    detailLoading.value = false
  }
}

async function reviewInstruction(row, action) {
  let remark = ''
  if (action === 'reject') {
    const { value } = await ElMessageBox.prompt(
      t('agent.ordersRejectPrompt'),
      t('agent.ordersRejectTitle'),
      { inputPattern: /.+/, inputErrorMessage: t('agent.ordersRejectRequired') }
    )
    remark = value
  }
  const result = await reviewAgentOrder(row.order_no, { action, remark })
  ElMessage.success(action === 'agree' ? t('agent.ordersAgreedMsg') : t('agent.ordersRejectedMsg'))
  stats.value = {
    ...stats.value,
    pending: Math.max(0, (stats.value.pending || 1) - 1),
    agreed: (stats.value.agreed || 0) + (action === 'agree' ? 1 : 0),
    rejected: (stats.value.rejected || 0) + (action === 'reject' ? 1 : 0)
  }
  if (filters.stage === 'needs_review') {
    rows.value = rows.value.filter((item) => item.order_no !== row.order_no)
    total.value = Math.max(0, total.value - 1)
  } else {
    patchRow(row.order_no, result)
  }
  if (detail.value?.order_no === row.order_no) detailVisible.value = false
}

async function requestPayout(row) {
  const result = await requestAgentPayout(row.order_no)
  ElMessage.success(t('agent.ordersPayoutRequestedMsg'))
  stats.value = {
    ...stats.value,
    awaiting_payout: Math.max(0, (stats.value.awaiting_payout || 1) - 1)
  }
  if (filters.stage === 'awaiting_payout') {
    rows.value = rows.value.filter((item) => item.order_no !== row.order_no)
    total.value = Math.max(0, total.value - 1)
  } else {
    patchRow(row.order_no, result)
  }
  if (detail.value?.order_no === row.order_no) {
    detail.value = { ...detail.value, ...result }
  }
}

onMounted(load)
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
.kpi { color: #8c8c8c; font-size: 13px; }
.ccy-pair { margin-left: 6px; color: #8c8c8c; font-size: 12px; }
.drawer-actions { margin-top: 16px; display: flex; gap: 8px; }
</style>
