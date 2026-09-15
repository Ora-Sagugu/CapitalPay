<template>
  <div>
    <h1 class="ptitle">{{ $t('orders.title') }}</h1>

    <div class="page-card">
      <div class="toolbar">
        <el-input
          v-model="prnQuery"
          class="prn-input"
          clearable
          :placeholder="$t('orders.prnPh')"
          @keyup.enter="searchByPrn"
          @clear="clearSearch"
        />
        <el-button type="primary" :loading="loading" @click="searchByPrn">
          {{ $t('orders.search') }}
        </el-button>
        <el-button v-if="activePrn" :disabled="loading" @click="clearSearch">
          {{ $t('orders.clear') }}
        </el-button>
      </div>
      <el-table
        :data="rows"
        v-loading="loading"
        row-class-name="order-row"
        @row-click="openDetail"
      >
        <el-table-column prop="order_no" :label="$t('orders.orderNo')" min-width="170" />
        <el-table-column prop="prn_code" :label="$t('orders.prn')" min-width="140">
          <template #default="{ row }">{{ row.prn_code || '—' }}</template>
        </el-table-column>
        <el-table-column :label="$t('common.amount')" min-width="140">
          <template #default="{ row }">
            {{ money(row.amount) }}
            <span v-if="row.from_currency || row.to_currency" class="ccy-pair">
              {{ row.from_currency || '—' }}/{{ row.to_currency || '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.status')" width="150">
          <template #default="{ row }">
            <el-tag :type="ORDER_STATUS_TYPE[row.status] || 'info'" size="small">
              {{ statusLabel(ORDER_STATUS, row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('orders.createdAt')" min-width="170">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!loading && !rows.length"
        :description="activePrn ? $t('orders.emptySearch') : $t('orders.empty')"
      />
      <el-pagination
        v-if="total > pageSize"
        class="pager"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer
      v-model="drawerVisible"
      :title="$t('orders.detailTitle')"
      size="520px"
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <template v-if="detail">
          <h3 class="section-title">{{ $t('orders.details') }}</h3>
          <el-descriptions :column="1" border size="small" class="detail-block">
            <el-descriptions-item :label="$t('orders.orderNo')">{{ detail.order_no }}</el-descriptions-item>
            <el-descriptions-item :label="$t('orders.prn')">{{ detail.prn_code || '—' }}</el-descriptions-item>
            <el-descriptions-item :label="$t('orders.currencyPair')">
              {{ detail.from_currency || '—' }} / {{ detail.to_currency || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('common.amount')">
              {{ money(detail.amount) }} {{ detail.from_currency || detail.currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.fee')">
              {{ money(detail.fee_amount || detail.fee) }} {{ detail.fee_currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.chargeBearer')">
              {{ statusLabel(FEE_BEARING, detail.fee_bearing) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.settleAmount')">
              {{ money(detail.settle_amount) }} {{ detail.to_currency || '' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('common.status')">
              <el-tag :type="ORDER_STATUS_TYPE[detail.status] || 'info'" size="small">
                {{ statusLabel(ORDER_STATUS, detail.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.beneficiaryName')">
              {{ detail.beneficiary_name || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.beneficiaryBank')">
              {{ detail.beneficiary_bank || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.beneficiaryAccount')">
              {{ detail.beneficiary_account || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.beneficiarySwift')">
              {{ detail.beneficiary_swift || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.beneficiaryAddress')">
              {{ detail.beneficiary_address || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('orders.purpose')">
              {{ detail.remittance_purpose || '—' }}
            </el-descriptions-item>
          </el-descriptions>

          <h3 class="section-title">{{ $t('orders.progress') }}</h3>
          <el-timeline>
            <el-timeline-item
              v-for="step in detail.timeline || []"
              :key="step.code"
              :timestamp="datetime(step.at)"
              :type="step.verified ? 'success' : (step.active ? 'primary' : 'info')"
              :hollow="!step.verified && !step.active"
            >
              {{ step.title }}
            </el-timeline-item>
          </el-timeline>

          <el-collapse v-if="detail.status_history?.length" class="history-collapse">
            <el-collapse-item :title="$t('orders.statusHistory')" name="history">
              <el-timeline>
                <el-timeline-item
                  v-for="(item, idx) in detail.status_history"
                  :key="idx"
                  :timestamp="datetime(item.at || item.time)"
                >
                  {{ item.status || item.from }} → {{ item.to || item.status }}
                </el-timeline-item>
              </el-timeline>
            </el-collapse-item>
          </el-collapse>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getRemittances, getPaymentHistory, getOrderDetail } from '@/api/payments'
import {
  money, datetime, ORDER_STATUS, ORDER_STATUS_TYPE, FEE_BEARING, statusLabel
} from '@/utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const prnQuery = ref('')
const activePrn = ref('')

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (activePrn.value) params.prn = activePrn.value
    const data = await getRemittances(params)
    rows.value = data.results || data.items || []
    total.value = data.count || data.total || 0
    if (!rows.value.length && !activePrn.value) {
      const hist = await getPaymentHistory({ page: page.value, page_size: pageSize })
      rows.value = (hist.items || []).map((i) => ({
        order_no: i.order_no,
        prn_code: i.prn_code || '',
        amount: i.amount,
        from_currency: i.currency,
        to_currency: i.currency,
        status: i.order_status,
        created_at: i.pay_time || i.created_at
      }))
      total.value = hist.total || 0
    }
  } finally {
    loading.value = false
  }
}

function searchByPrn() {
  activePrn.value = (prnQuery.value || '').trim()
  page.value = 1
  load()
}

function clearSearch() {
  prnQuery.value = ''
  activePrn.value = ''
  page.value = 1
  load()
}

function onPage(p) {
  page.value = p
  load()
}

async function openDetail(row) {
  drawerVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getOrderDetail(row.order_no)
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.ptitle { margin: 0 0 16px; font-size: 22px; }
.page-card { background: #fff; padding: 16px; border-radius: 8px; }
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.prn-input { width: 260px; max-width: 100%; }
.pager { margin-top: 12px; }
.ccy-pair { margin-left: 6px; color: #8c8c8c; font-size: 12px; }
.section-title { margin: 20px 0 12px; font-size: 15px; font-weight: 600; }
.section-title:first-child { margin-top: 0; }
.detail-block { margin-bottom: 8px; }
.history-collapse { margin-top: 16px; }
:deep(.order-row) { cursor: pointer; }
</style>
