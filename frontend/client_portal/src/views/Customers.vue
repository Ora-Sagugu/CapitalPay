<template>
  <div>
    <PageHeader title="Customers" subtitle="End-customer profiles under merchants" />
    <div class="page-card">
      <div class="toolbar">
        <el-input
          v-model="filters.search"
          placeholder="Customer no. / name / email"
          clearable
          style="width: 240px"
          @clear="reload"
          @keyup.enter="reload"
        />
        <el-input
          v-model="filters.merchant_no"
          placeholder="Merchant no."
          clearable
          style="width: 160px"
          @clear="reload"
          @keyup.enter="reload"
        />
        <el-select
          v-model="filters.kyc_status"
          placeholder="KYC"
          clearable
          style="width: 140px"
          @change="reload"
        >
          <el-option label="Draft" value="draft" />
          <el-option label="Submitted" value="submitted" />
          <el-option label="Approved" value="approved" />
          <el-option label="Rejected" value="rejected" />
        </el-select>
        <el-button type="primary" @click="reload">Search</el-button>
        <el-button @click="resetFilters">Reset</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="customer_no" label="Customer no." min-width="140" />
        <el-table-column prop="legal_name" label="Legal name" min-width="160" />
        <el-table-column prop="merchant_no" label="Merchant no." min-width="130" />
        <el-table-column prop="merchant_name" label="Merchant" min-width="150" />
        <el-table-column prop="agent_no" label="Agent Code" min-width="120" />
        <el-table-column label="KYC" min-width="110">
          <template #default="{ row }">
            <el-tag :type="kycType(row.kyc_status)" size="small">{{ kycLabel(row.kyc_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact_email" label="Email" min-width="180" />
        <el-table-column label="ID Type" min-width="120">
          <template #default="{ row }">{{ idTypeLabel(row.id_type) }}</template>
        </el-table-column>
        <el-table-column prop="id_number" label="ID No." min-width="140" />
        <el-table-column prop="nationality" label="Country" min-width="110" />
        <el-table-column prop="address" label="Address" min-width="180" show-overflow-tooltip />
        <el-table-column label="Created" min-width="165">
          <template #default="{ row }">{{ datetime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">View</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="toolbar"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="480px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="Customer no.">{{ dash(detail.customer_no) }}</el-descriptions-item>
        <el-descriptions-item label="Legal name">{{ dash(detail.legal_name) }}</el-descriptions-item>
        <el-descriptions-item label="Merchant">{{ dash(detail.merchant_name) }} ({{ dash(detail.merchant_no) }})</el-descriptions-item>
        <el-descriptions-item label="Agent Code">{{ dash(detail.agent_no) }}</el-descriptions-item>
        <el-descriptions-item label="KYC">{{ kycLabel(detail.kyc_status) }}</el-descriptions-item>
        <el-descriptions-item label="Email">{{ dash(detail.contact_email) }}</el-descriptions-item>
        <el-descriptions-item label="ID Type">{{ idTypeLabel(detail.id_type) }}</el-descriptions-item>
        <el-descriptions-item label="ID No.">{{ dash(detail.id_number) }}</el-descriptions-item>
        <el-descriptions-item label="Country">{{ dash(detail.nationality) }}</el-descriptions-item>
        <el-descriptions-item label="Address">{{ dash(detail.address) }}</el-descriptions-item>
        <el-descriptions-item label="Created">{{ datetime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="Updated">{{ datetime(detail.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getCustomers } from '@/api/customers'
import { datetime, unwrapList } from '@/utils/format'

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({ search: '', merchant_no: '', kyc_status: '' })
const detailVisible = ref(false)
const detail = ref(null)

const detailTitle = computed(() => {
  if (!detail.value) return 'Customer'
  return detail.value.legal_name || detail.value.customer_no || 'Customer'
})

const ID_TYPE_LABELS = {
  id_card: 'ID No.',
  passport: 'Passport',
  business_license: 'Business Licence',
  other: 'Other',
  ID_CARD: 'ID No.',
  PASSPORT: 'Passport',
  BUSINESS_LICENSE: 'Business Licence',
  OTHER: 'Other'
}

function dash(value) {
  return value || '—'
}

function idTypeLabel(code) {
  if (!code) return '—'
  return ID_TYPE_LABELS[code] || code
}

function kycLabel(code) {
  const map = {
    draft: 'Draft',
    submitted: 'Submitted',
    approved: 'Approved',
    rejected: 'Rejected'
  }
  return map[String(code || '').toLowerCase()] || code || '—'
}

function kycType(code) {
  const value = String(code || '').toLowerCase()
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'danger'
  if (value === 'submitted') return 'warning'
  return 'info'
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

function resetFilters() {
  filters.search = ''
  filters.merchant_no = ''
  filters.kyc_status = ''
  page.value = 1
  reload()
}

function onPage(value) {
  page.value = value
  reload()
}

async function reload() {
  loading.value = true
  try {
    const data = unwrapList(await getCustomers({
      page: page.value,
      page_size: pageSize,
      search: filters.search || undefined,
      merchant__merchant_no: filters.merchant_no || undefined,
      kyc_status: filters.kyc_status || undefined
    }))
    rows.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>
