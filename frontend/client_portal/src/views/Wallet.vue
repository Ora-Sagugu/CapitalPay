<template>
  <div>
    <PageHeader
      title="Wallet"
      subtitle="Platform, customer, and agent wallet balances — demo UI for display only"
    />

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="Demo mode — balances and ledger are local mock data and are not persisted."
      class="demo-alert"
    />

    <KpiCards :items="kpis" />

    <div class="page-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Overview" name="overview">
          <p class="section-hint">Platform treasury by currency. Click a card to filter the ledger.</p>
          <div class="balance-grid">
            <div
              v-for="item in treasury"
              :key="item.currency"
              class="balance-card"
              :class="{ active: ledgerCurrency === item.currency }"
              @click="selectTreasury(item.currency)"
            >
              <div class="balance-top">
                <span class="ccy">{{ item.currency }}</span>
                <el-tag :type="item.status === 'FROZEN' ? 'warning' : 'success'" size="small" effect="plain">
                  {{ item.status === 'FROZEN' ? 'Frozen' : 'Active' }}
                </el-tag>
              </div>
              <div class="balance-amount">{{ money(item.balance) }}</div>
              <div class="balance-meta">
                <span>Available {{ money(item.available) }}</span>
                <span v-if="Number(item.frozen) > 0">Frozen {{ money(item.frozen) }}</span>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Customer wallets" name="customers">
          <div class="toolbar">
            <el-input
              v-model="customerFilter"
              placeholder="Customer / wallet ID"
              clearable
              style="width: 220px"
            />
            <el-select v-model="customerCurrency" placeholder="Currency" clearable style="width: 120px">
              <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="customerStatus" placeholder="Status" clearable style="width: 130px">
              <el-option label="Active" value="ACTIVE" />
              <el-option label="Frozen" value="FROZEN" />
            </el-select>
          </div>
          <el-table :data="filteredCustomers" max-height="480">
            <el-table-column prop="wallet_id" label="Wallet ID" min-width="120" />
            <el-table-column prop="owner_name" label="Customer" min-width="160" />
            <el-table-column prop="currency" label="Currency" width="100" />
            <el-table-column label="Balance" min-width="120">
              <template #default="{ row }">{{ money(row.balance) }}</template>
            </el-table-column>
            <el-table-column label="Available" min-width="120">
              <template #default="{ row }">{{ money(row.available) }}</template>
            </el-table-column>
            <el-table-column label="Frozen" min-width="110">
              <template #default="{ row }">{{ money(row.frozen) }}</template>
            </el-table-column>
            <el-table-column label="Status" width="110">
              <template #default="{ row }">
                <el-tag :type="row.status === 'FROZEN' ? 'warning' : 'success'" size="small" effect="plain">
                  {{ row.status === 'FROZEN' ? 'Frozen' : 'Active' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Updated" min-width="160">
              <template #default="{ row }">{{ datetime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="Actions" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row)">Details</el-button>
                <el-button link type="primary" @click="openAdjust(row, 'credit')">Credit</el-button>
                <el-button
                  v-if="row.status !== 'FROZEN'"
                  link
                  type="warning"
                  @click="toggleFreeze(row)"
                >
                  Freeze
                </el-button>
                <el-button v-else link type="success" @click="toggleFreeze(row)">Unfreeze</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Agent wallets" name="agents">
          <div class="toolbar">
            <el-input
              v-model="agentFilter"
              placeholder="Agent / wallet ID"
              clearable
              style="width: 220px"
            />
            <el-select v-model="agentCurrency" placeholder="Currency" clearable style="width: 120px">
              <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="agentStatus" placeholder="Status" clearable style="width: 130px">
              <el-option label="Active" value="ACTIVE" />
              <el-option label="Frozen" value="FROZEN" />
            </el-select>
          </div>
          <el-table :data="filteredAgents" max-height="480">
            <el-table-column prop="wallet_id" label="Wallet ID" min-width="120" />
            <el-table-column prop="owner_name" label="Agent" min-width="160" />
            <el-table-column prop="agent_code" label="Agent code" min-width="120" />
            <el-table-column prop="currency" label="Currency" width="100" />
            <el-table-column label="Balance" min-width="120">
              <template #default="{ row }">{{ money(row.balance) }}</template>
            </el-table-column>
            <el-table-column label="Available" min-width="120">
              <template #default="{ row }">{{ money(row.available) }}</template>
            </el-table-column>
            <el-table-column label="Frozen" min-width="110">
              <template #default="{ row }">{{ money(row.frozen) }}</template>
            </el-table-column>
            <el-table-column label="Status" width="110">
              <template #default="{ row }">
                <el-tag :type="row.status === 'FROZEN' ? 'warning' : 'success'" size="small" effect="plain">
                  {{ row.status === 'FROZEN' ? 'Frozen' : 'Active' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Updated" min-width="160">
              <template #default="{ row }">{{ datetime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="Actions" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row)">Details</el-button>
                <el-button link type="primary" @click="openAdjust(row, 'credit')">Credit</el-button>
                <el-button
                  v-if="row.status !== 'FROZEN'"
                  link
                  type="warning"
                  @click="toggleFreeze(row)"
                >
                  Freeze
                </el-button>
                <el-button v-else link type="success" @click="toggleFreeze(row)">Unfreeze</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Ledger" name="ledger">
          <div class="toolbar">
            <el-select v-model="ledgerOwnerType" placeholder="Owner type" clearable style="width: 140px">
              <el-option label="Platform" value="PLATFORM" />
              <el-option label="Customer" value="CUSTOMER" />
              <el-option label="Agent" value="AGENT" />
            </el-select>
            <el-select v-model="ledgerType" placeholder="Type" clearable style="width: 150px">
              <el-option label="Top up" value="TOP_UP" />
              <el-option label="Withdraw" value="WITHDRAW" />
              <el-option label="Credit" value="CREDIT" />
              <el-option label="Debit" value="DEBIT" />
              <el-option label="Transfer in" value="TRANSFER_IN" />
              <el-option label="Transfer out" value="TRANSFER_OUT" />
              <el-option label="Freeze" value="FREEZE" />
              <el-option label="Unfreeze" value="UNFREEZE" />
            </el-select>
            <el-select v-model="ledgerCurrency" placeholder="Currency" clearable style="width: 120px">
              <el-option v-for="c in currencies" :key="c" :label="c" :value="c" />
            </el-select>
            <el-button @click="resetLedgerFilters">Reset filters</el-button>
          </div>
          <el-table :data="filteredLedger" max-height="480">
            <el-table-column prop="id" label="Txn ID" min-width="120" />
            <el-table-column label="Owner" min-width="150">
              <template #default="{ row }">
                <div>{{ row.owner_name }}</div>
                <div class="muted">{{ ownerTypeLabel(row.owner_type) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="Type" min-width="120">
              <template #default="{ row }">{{ typeLabel(row.type) }}</template>
            </el-table-column>
            <el-table-column prop="currency" label="Currency" width="100" />
            <el-table-column label="Amount" min-width="130">
              <template #default="{ row }">
                <span :class="isCredit(row.type) ? 'amt-in' : 'amt-out'">{{ signedAmount(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="Balance after" min-width="130">
              <template #default="{ row }">{{ money(row.balance_after) }}</template>
            </el-table-column>
            <el-table-column label="Status" width="110">
              <template #default="{ row }">
                <el-tag :type="row.status === 'SUCCESS' ? 'success' : 'warning'" size="small" effect="plain">
                  {{ row.status === 'SUCCESS' ? 'Success' : 'Pending' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Time" min-width="170">
              <template #default="{ row }">{{ datetime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="Narrative" min-width="180" show-overflow-tooltip />
          </el-table>
          <el-empty v-if="!filteredLedger.length" description="No ledger rows for the current filters" />
        </el-tab-pane>

        <el-tab-pane label="Requests" name="requests">
          <p class="section-hint">Pending top-up / withdraw requests awaiting ops review (demo).</p>
          <el-table :data="requests" max-height="480">
            <el-table-column prop="request_no" label="Request" min-width="130" />
            <el-table-column label="Owner" min-width="150">
              <template #default="{ row }">
                <div>{{ row.owner_name }}</div>
                <div class="muted">{{ ownerTypeLabel(row.owner_type) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="Type" width="120">
              <template #default="{ row }">{{ row.type === 'TOP_UP' ? 'Top up' : 'Withdraw' }}</template>
            </el-table-column>
            <el-table-column prop="currency" label="Currency" width="100" />
            <el-table-column label="Amount" min-width="120">
              <template #default="{ row }">{{ money(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'PENDING' ? 'warning' : row.status === 'APPROVED' ? 'success' : 'danger'"
                  size="small"
                  effect="plain"
                >
                  {{ requestStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Submitted" min-width="170">
              <template #default="{ row }">{{ datetime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="Narrative" min-width="160" show-overflow-tooltip />
            <el-table-column label="Actions" width="160" fixed="right">
              <template #default="{ row }">
                <template v-if="row.status === 'PENDING'">
                  <el-button link type="success" @click="reviewRequest(row, 'APPROVED')">Approve</el-button>
                  <el-button link type="danger" @click="reviewRequest(row, 'REJECTED')">Reject</el-button>
                </template>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <div class="footer-bar">
        <el-button @click="resetDemo">Reset demo data</el-button>
      </div>
    </div>

    <el-drawer v-model="detailVisible" title="Wallet details" size="420px" destroy-on-close>
      <template v-if="detailRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="Wallet ID">{{ detailRow.wallet_id }}</el-descriptions-item>
          <el-descriptions-item label="Owner">{{ detailRow.owner_name }}</el-descriptions-item>
          <el-descriptions-item label="Type">{{ ownerTypeLabel(detailRow.owner_type) }}</el-descriptions-item>
          <el-descriptions-item v-if="detailRow.agent_code" label="Agent code">
            {{ detailRow.agent_code }}
          </el-descriptions-item>
          <el-descriptions-item label="Currency">{{ detailRow.currency }}</el-descriptions-item>
          <el-descriptions-item label="Balance">{{ money(detailRow.balance) }}</el-descriptions-item>
          <el-descriptions-item label="Available">{{ money(detailRow.available) }}</el-descriptions-item>
          <el-descriptions-item label="Frozen">{{ money(detailRow.frozen) }}</el-descriptions-item>
          <el-descriptions-item label="Status">
            {{ detailRow.status === 'FROZEN' ? 'Frozen' : 'Active' }}
          </el-descriptions-item>
          <el-descriptions-item label="Updated">{{ datetime(detailRow.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions">
          <el-button type="primary" @click="openAdjust(detailRow, 'credit')">Credit</el-button>
          <el-button @click="openAdjust(detailRow, 'debit')">Debit</el-button>
          <el-button
            :type="detailRow.status === 'FROZEN' ? 'success' : 'warning'"
            plain
            @click="toggleFreeze(detailRow)"
          >
            {{ detailRow.status === 'FROZEN' ? 'Unfreeze' : 'Freeze' }}
          </el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      v-model="adjustVisible"
      :title="adjustMode === 'credit' ? 'Credit wallet' : 'Debit wallet'"
      width="440px"
      destroy-on-close
      @closed="resetAdjustForm"
    >
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="Wallet">
          <el-input :model-value="adjustForm.wallet_id" disabled />
        </el-form-item>
        <el-form-item label="Owner">
          <el-input :model-value="adjustForm.owner_name" disabled />
        </el-form-item>
        <el-form-item label="Currency">
          <el-input :model-value="adjustForm.currency" disabled />
        </el-form-item>
        <el-form-item label="Amount">
          <el-input v-model="adjustForm.amount" placeholder="e.g. 100.00" />
        </el-form-item>
        <el-form-item label="Narrative">
          <el-input v-model="adjustForm.remark" placeholder="Optional remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAdjust">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import KpiCards from '@/components/KpiCards.vue'
import { datetime, money } from '@/utils/format'

const now = Date.now()

function hoursAgo(h) {
  return new Date(now - h * 3600e3).toISOString()
}

function daysAgo(d) {
  return new Date(now - d * 86400e3).toISOString()
}

const DEMO_TREASURY = [
  { currency: 'USD', balance: '2480320.55', available: '2380320.55', frozen: '100000.00', status: 'ACTIVE' },
  { currency: 'EUR', balance: '612450.00', available: '612450.00', frozen: '0.00', status: 'ACTIVE' },
  { currency: 'KES', balance: '18500000.00', available: '17500000.00', frozen: '1000000.00', status: 'ACTIVE' },
  { currency: 'CNY', balance: '920000.00', available: '920000.00', frozen: '0.00', status: 'ACTIVE' }
]

const DEMO_CUSTOMERS = [
  {
    wallet_id: 'CW-10021',
    owner_type: 'CUSTOMER',
    owner_name: 'Horizon Trade Limited',
    currency: 'USD',
    balance: '12580.50',
    available: '12580.50',
    frozen: '0.00',
    status: 'ACTIVE',
    updated_at: hoursAgo(2)
  },
  {
    wallet_id: 'CW-10022',
    owner_type: 'CUSTOMER',
    owner_name: 'Lagos Agro Commodities',
    currency: 'USD',
    balance: '176032.25',
    available: '166032.25',
    frozen: '10000.00',
    status: 'ACTIVE',
    updated_at: hoursAgo(5)
  },
  {
    wallet_id: 'CW-10023',
    owner_type: 'CUSTOMER',
    owner_name: 'Nairobi Retail Hub',
    currency: 'KES',
    balance: '250000.00',
    available: '0.00',
    frozen: '250000.00',
    status: 'FROZEN',
    updated_at: daysAgo(1)
  },
  {
    wallet_id: 'CW-10024',
    owner_type: 'CUSTOMER',
    owner_name: 'Pearl Import Co.',
    currency: 'EUR',
    balance: '4320.00',
    available: '3820.00',
    frozen: '500.00',
    status: 'ACTIVE',
    updated_at: daysAgo(2)
  },
  {
    wallet_id: 'CW-10025',
    owner_type: 'CUSTOMER',
    owner_name: 'Shenzhen Electronics',
    currency: 'CNY',
    balance: '88000.00',
    available: '88000.00',
    frozen: '0.00',
    status: 'ACTIVE',
    updated_at: daysAgo(3)
  }
]

const DEMO_AGENTS = [
  {
    wallet_id: 'AW-3001',
    owner_type: 'AGENT',
    owner_name: 'Grace Nyambura',
    agent_code: 'AG20260003',
    currency: 'USD',
    balance: '45200.00',
    available: '45200.00',
    frozen: '0.00',
    status: 'ACTIVE',
    updated_at: hoursAgo(1)
  },
  {
    wallet_id: 'AW-3002',
    owner_type: 'AGENT',
    owner_name: 'East Africa Desk',
    agent_code: 'AG20260011',
    currency: 'KES',
    balance: '980000.00',
    available: '880000.00',
    frozen: '100000.00',
    status: 'ACTIVE',
    updated_at: hoursAgo(8)
  },
  {
    wallet_id: 'AW-3003',
    owner_type: 'AGENT',
    owner_name: 'Coastal Partners',
    agent_code: 'AG20260018',
    currency: 'EUR',
    balance: '12500.00',
    available: '0.00',
    frozen: '12500.00',
    status: 'FROZEN',
    updated_at: daysAgo(1)
  }
]

function seedLedger() {
  return [
    {
      id: 'WTX-9012',
      owner_type: 'CUSTOMER',
      owner_name: 'Horizon Trade Limited',
      type: 'TOP_UP',
      currency: 'USD',
      amount: '2000.00',
      balance_after: '12580.50',
      status: 'SUCCESS',
      remark: 'Bank transfer credit / PRN A25503',
      created_at: hoursAgo(1)
    },
    {
      id: 'WTX-9011',
      owner_type: 'AGENT',
      owner_name: 'Grace Nyambura',
      type: 'CREDIT',
      currency: 'USD',
      amount: '1200.00',
      balance_after: '45200.00',
      status: 'SUCCESS',
      remark: 'Commission settlement',
      created_at: hoursAgo(3)
    },
    {
      id: 'WTX-9010',
      owner_type: 'PLATFORM',
      owner_name: 'Platform treasury',
      type: 'DEBIT',
      currency: 'USD',
      amount: '9800.00',
      balance_after: '2480320.55',
      status: 'SUCCESS',
      remark: 'Payout cover — PAY202609120002',
      created_at: hoursAgo(4)
    },
    {
      id: 'WTX-9009',
      owner_type: 'CUSTOMER',
      owner_name: 'Pearl Import Co.',
      type: 'TRANSFER_OUT',
      currency: 'EUR',
      amount: '500.00',
      balance_after: '4320.00',
      status: 'SUCCESS',
      remark: 'Hold for remittance',
      created_at: daysAgo(1)
    },
    {
      id: 'WTX-9008',
      owner_type: 'CUSTOMER',
      owner_name: 'Nairobi Retail Hub',
      type: 'FREEZE',
      currency: 'KES',
      amount: '250000.00',
      balance_after: '250000.00',
      status: 'SUCCESS',
      remark: 'Compliance hold',
      created_at: daysAgo(1)
    },
    {
      id: 'WTX-9007',
      owner_type: 'CUSTOMER',
      owner_name: 'Lagos Agro Commodities',
      type: 'WITHDRAW',
      currency: 'USD',
      amount: '5000.00',
      balance_after: '176032.25',
      status: 'PENDING',
      remark: 'External bank payout',
      created_at: daysAgo(2)
    },
    {
      id: 'WTX-9006',
      owner_type: 'AGENT',
      owner_name: 'East Africa Desk',
      type: 'TOP_UP',
      currency: 'KES',
      amount: '200000.00',
      balance_after: '980000.00',
      status: 'SUCCESS',
      remark: 'Agent float top-up',
      created_at: daysAgo(3)
    }
  ]
}

const DEMO_REQUESTS = [
  {
    request_no: 'WR-4401',
    owner_type: 'CUSTOMER',
    owner_name: 'Lagos Agro Commodities',
    wallet_id: 'CW-10022',
    type: 'WITHDRAW',
    currency: 'USD',
    amount: '5000.00',
    status: 'PENDING',
    remark: 'External bank payout',
    created_at: daysAgo(2)
  },
  {
    request_no: 'WR-4402',
    owner_type: 'AGENT',
    owner_name: 'Grace Nyambura',
    wallet_id: 'AW-3001',
    type: 'TOP_UP',
    currency: 'USD',
    amount: '3000.00',
    status: 'PENDING',
    remark: 'Float replenishment',
    created_at: hoursAgo(6)
  },
  {
    request_no: 'WR-4398',
    owner_type: 'CUSTOMER',
    owner_name: 'Shenzhen Electronics',
    wallet_id: 'CW-10025',
    type: 'TOP_UP',
    currency: 'CNY',
    amount: '20000.00',
    status: 'APPROVED',
    remark: 'Approved bank credit',
    created_at: daysAgo(4)
  }
]

const activeTab = ref('overview')
const treasury = ref(structuredClone(DEMO_TREASURY))
const customers = ref(structuredClone(DEMO_CUSTOMERS))
const agents = ref(structuredClone(DEMO_AGENTS))
const ledger = ref(seedLedger())
const requests = ref(structuredClone(DEMO_REQUESTS))

const customerFilter = ref('')
const customerCurrency = ref('')
const customerStatus = ref('')
const agentFilter = ref('')
const agentCurrency = ref('')
const agentStatus = ref('')
const ledgerOwnerType = ref('')
const ledgerType = ref('')
const ledgerCurrency = ref('')

const detailVisible = ref(false)
const detailRow = ref(null)
const adjustVisible = ref(false)
const adjustMode = ref('credit')
const submitting = ref(false)
const adjustForm = reactive({
  wallet_id: '',
  owner_name: '',
  owner_type: '',
  currency: '',
  amount: '',
  remark: ''
})

let txnSeq = 9013

const currencies = computed(() => ['USD', 'EUR', 'KES', 'CNY'])

const kpis = computed(() => {
  const all = [...customers.value, ...agents.value]
  const active = all.filter((w) => w.status === 'ACTIVE').length
  const frozen = all.filter((w) => w.status === 'FROZEN').length
  const pending = requests.value.filter((r) => r.status === 'PENDING').length
  const usdTreasury = treasury.value.find((t) => t.currency === 'USD')
  return [
    { label: 'USD treasury', value: money(usdTreasury?.balance || 0), icon: 'Money', hint: 'Platform float' },
    { label: 'Active wallets', value: String(active), icon: 'Wallet', hint: 'Customer + agent' },
    { label: 'Frozen wallets', value: String(frozen), icon: 'Lock', color: '#e6a23c', bg: '#fdf6ec' },
    { label: 'Pending requests', value: String(pending), icon: 'Bell', color: '#409eff', bg: '#ecf5ff' }
  ]
})

const filteredCustomers = computed(() => filterWallets(customers.value, customerFilter.value, customerCurrency.value, customerStatus.value))
const filteredAgents = computed(() => filterWallets(agents.value, agentFilter.value, agentCurrency.value, agentStatus.value))

const filteredLedger = computed(() =>
  ledger.value.filter((row) => {
    if (ledgerOwnerType.value && row.owner_type !== ledgerOwnerType.value) return false
    if (ledgerType.value && row.type !== ledgerType.value) return false
    if (ledgerCurrency.value && row.currency !== ledgerCurrency.value) return false
    return true
  })
)

function filterWallets(list, q, ccy, status) {
  const needle = (q || '').trim().toLowerCase()
  return list.filter((row) => {
    if (ccy && row.currency !== ccy) return false
    if (status && row.status !== status) return false
    if (!needle) return true
    return (
      row.wallet_id.toLowerCase().includes(needle) ||
      row.owner_name.toLowerCase().includes(needle) ||
      (row.agent_code || '').toLowerCase().includes(needle)
    )
  })
}

function dec(v) {
  return Number(v || 0)
}

function fmt(n) {
  return (Math.round(n * 100) / 100).toFixed(2)
}

function ownerTypeLabel(type) {
  if (type === 'PLATFORM') return 'Platform'
  if (type === 'AGENT') return 'Agent'
  return 'Customer'
}

function typeLabel(type) {
  const map = {
    TOP_UP: 'Top up',
    WITHDRAW: 'Withdraw',
    CREDIT: 'Credit',
    DEBIT: 'Debit',
    TRANSFER_IN: 'Transfer in',
    TRANSFER_OUT: 'Transfer out',
    FREEZE: 'Freeze',
    UNFREEZE: 'Unfreeze'
  }
  return map[type] || type
}

function requestStatusLabel(status) {
  if (status === 'APPROVED') return 'Approved'
  if (status === 'REJECTED') return 'Rejected'
  return 'Pending'
}

function isCredit(type) {
  return type === 'TOP_UP' || type === 'CREDIT' || type === 'TRANSFER_IN' || type === 'UNFREEZE'
}

function signedAmount(row) {
  return `${isCredit(row.type) ? '+' : '-'}${money(row.amount)}`
}

function selectTreasury(ccy) {
  ledgerCurrency.value = ccy
  activeTab.value = 'ledger'
}

function resetLedgerFilters() {
  ledgerOwnerType.value = ''
  ledgerType.value = ''
  ledgerCurrency.value = ''
}

function openDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

function openAdjust(row, mode) {
  adjustMode.value = mode
  adjustForm.wallet_id = row.wallet_id
  adjustForm.owner_name = row.owner_name
  adjustForm.owner_type = row.owner_type
  adjustForm.currency = row.currency
  adjustForm.amount = ''
  adjustForm.remark = ''
  adjustVisible.value = true
}

function resetAdjustForm() {
  adjustForm.wallet_id = ''
  adjustForm.owner_name = ''
  adjustForm.owner_type = ''
  adjustForm.currency = ''
  adjustForm.amount = ''
  adjustForm.remark = ''
}

function findWallet(walletId) {
  return (
    customers.value.find((w) => w.wallet_id === walletId) ||
    agents.value.find((w) => w.wallet_id === walletId) ||
    null
  )
}

function pushLedger(partial) {
  ledger.value.unshift({
    id: `WTX-${txnSeq++}`,
    status: 'SUCCESS',
    remark: '',
    created_at: new Date().toISOString(),
    ...partial
  })
}

function touch(row) {
  row.updated_at = new Date().toISOString()
}

async function submitAdjust() {
  const amount = Number(adjustForm.amount)
  if (!amount || amount <= 0) {
    ElMessage.warning('Enter a valid amount')
    return
  }
  const wallet = findWallet(adjustForm.wallet_id)
  if (!wallet) {
    ElMessage.warning('Wallet not found')
    return
  }
  if (wallet.status === 'FROZEN' && adjustMode.value === 'debit') {
    ElMessage.warning('Frozen wallet cannot be debited')
    return
  }

  submitting.value = true
  try {
    await new Promise((r) => setTimeout(r, 280))
    if (adjustMode.value === 'credit') {
      wallet.balance = fmt(dec(wallet.balance) + amount)
      wallet.available = fmt(dec(wallet.available) + amount)
      pushLedger({
        owner_type: wallet.owner_type,
        owner_name: wallet.owner_name,
        type: 'CREDIT',
        currency: wallet.currency,
        amount: fmt(amount),
        balance_after: wallet.balance,
        remark: adjustForm.remark || 'Ops credit (demo)'
      })
      ElMessage.success('Wallet credited (demo)')
    } else {
      if (dec(wallet.available) < amount) {
        ElMessage.warning('Insufficient available balance')
        return
      }
      wallet.balance = fmt(dec(wallet.balance) - amount)
      wallet.available = fmt(dec(wallet.available) - amount)
      pushLedger({
        owner_type: wallet.owner_type,
        owner_name: wallet.owner_name,
        type: 'DEBIT',
        currency: wallet.currency,
        amount: fmt(amount),
        balance_after: wallet.balance,
        remark: adjustForm.remark || 'Ops debit (demo)'
      })
      ElMessage.success('Wallet debited (demo)')
    }
    touch(wallet)
    adjustVisible.value = false
  } finally {
    submitting.value = false
  }
}

function toggleFreeze(row) {
  const wallet = findWallet(row.wallet_id) || row
  if (wallet.status === 'FROZEN') {
    const frozen = dec(wallet.frozen)
    wallet.status = 'ACTIVE'
    wallet.available = fmt(dec(wallet.available) + frozen)
    wallet.frozen = '0.00'
    pushLedger({
      owner_type: wallet.owner_type,
      owner_name: wallet.owner_name,
      type: 'UNFREEZE',
      currency: wallet.currency,
      amount: fmt(frozen),
      balance_after: wallet.balance,
      remark: 'Ops unfreeze (demo)'
    })
    ElMessage.success('Wallet unfrozen (demo)')
  } else {
    const avail = dec(wallet.available)
    wallet.status = 'FROZEN'
    wallet.frozen = fmt(dec(wallet.frozen) + avail)
    wallet.available = '0.00'
    pushLedger({
      owner_type: wallet.owner_type,
      owner_name: wallet.owner_name,
      type: 'FREEZE',
      currency: wallet.currency,
      amount: fmt(avail),
      balance_after: wallet.balance,
      remark: 'Ops freeze (demo)'
    })
    ElMessage.success('Wallet frozen (demo)')
  }
  touch(wallet)
  if (detailRow.value?.wallet_id === wallet.wallet_id) {
    detailRow.value = wallet
  }
}

function reviewRequest(row, status) {
  row.status = status
  if (status === 'APPROVED') {
    const wallet = findWallet(row.wallet_id)
    if (wallet && row.type === 'TOP_UP') {
      const amount = dec(row.amount)
      wallet.balance = fmt(dec(wallet.balance) + amount)
      wallet.available = fmt(dec(wallet.available) + amount)
      touch(wallet)
      pushLedger({
        owner_type: row.owner_type,
        owner_name: row.owner_name,
        type: 'TOP_UP',
        currency: row.currency,
        amount: row.amount,
        balance_after: wallet.balance,
        remark: `Approved ${row.request_no}`
      })
    }
    ElMessage.success('Request approved (demo)')
  } else {
    ElMessage.success('Request rejected (demo)')
  }
}

function resetDemo() {
  treasury.value = structuredClone(DEMO_TREASURY)
  customers.value = structuredClone(DEMO_CUSTOMERS)
  agents.value = structuredClone(DEMO_AGENTS)
  ledger.value = seedLedger()
  requests.value = structuredClone(DEMO_REQUESTS)
  txnSeq = 9013
  customerFilter.value = ''
  customerCurrency.value = ''
  customerStatus.value = ''
  agentFilter.value = ''
  agentCurrency.value = ''
  agentStatus.value = ''
  resetLedgerFilters()
  activeTab.value = 'overview'
  ElMessage.success('Demo data reset')
}
</script>

<style scoped>
.demo-alert { margin-bottom: 14px; }
.section-hint { margin: 0 0 12px; color: #8c8c8c; font-size: 13px; }
.balance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}
.balance-card {
  background: #faf8f5;
  border-radius: 10px;
  padding: 16px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.balance-card:hover { box-shadow: 0 2px 10px rgba(224, 112, 48, 0.12); }
.balance-card.active { border-color: var(--tech-orange, #f08040); background: #fff; }
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
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.footer-bar {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0ebe4;
}
.muted { color: #8c8c8c; font-size: 12px; }
.amt-in { color: #2f9e44; font-weight: 600; }
.amt-out { color: #c0392b; font-weight: 600; }
.drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
</style>
