<template>
  <div>
    <PageHeader :title="$t('pages.reconciliation.title')" :subtitle="$t('pages.reconciliation.subtitle')" />
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane :label="$t('pages.reconciliation.tabBatches')" name="batches" />
      <el-tab-pane :label="$t('pages.reconciliation.tabResults')" name="results" />
      <el-tab-pane :label="$t('pages.reconciliation.tabDiffs')" name="diffs" />
      <el-tab-pane :label="$t('pages.reconciliation.tabNostro')" name="nostro" />
      <el-tab-pane :label="$t('pages.reconciliation.tabAlerts')" name="alerts" />
    </el-tabs>
    <div class="page-card">
      <el-table v-if="tab === 'batches'" :data="batches" v-loading="loading">
        <el-table-column prop="batch_no" :label="$t('pages.reconciliation.batchNo')" min-width="150" />
        <el-table-column prop="bank_code" label="Bank Code" min-width="110" />
        <el-table-column prop="bank_name" :label="$t('pages.reconciliation.bank')" min-width="140" />
        <el-table-column prop="recon_type" :label="$t('pages.reconciliation.type')" width="130" />
        <el-table-column prop="reconciliation_date" :label="$t('pages.reconciliation.date')" min-width="120" />
        <el-table-column prop="status" :label="$t('pages.reconciliation.progress')" width="110" />
        <el-table-column prop="match_count" :label="$t('pages.reconciliation.matched')" width="90" />
        <el-table-column prop="diff_count" :label="$t('pages.reconciliation.diffs')" width="80" />
      </el-table>
      <el-table v-else-if="tab === 'results'" :data="batches" v-loading="loading">
        <el-table-column prop="batch_no" :label="$t('pages.reconciliation.batchNo')" min-width="150" />
        <el-table-column prop="total_count_bank" :label="$t('pages.reconciliation.bankCount')" min-width="110" />
        <el-table-column prop="total_count_platform" :label="$t('pages.reconciliation.platformCount')" min-width="130" />
        <el-table-column prop="match_count" :label="$t('pages.reconciliation.match')" width="80" />
        <el-table-column prop="diff_count" :label="$t('pages.reconciliation.diffs')" width="80" />
        <el-table-column prop="status" :label="$t('common.status')" width="110" />
      </el-table>
      <el-table v-else-if="tab === 'diffs'" :data="diffs" v-loading="loading">
        <el-table-column prop="id" :label="$t('pages.reconciliation.diffs')" min-width="140" />
        <el-table-column prop="order_no" :label="$t('pages.reconciliation.orderNo')" min-width="150" />
        <el-table-column prop="diff_type" :label="$t('pages.reconciliation.type')" min-width="110" />
        <el-table-column prop="amount_bank" :label="$t('pages.reconciliation.bankAmount')" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="amount_platform" :label="$t('pages.reconciliation.platformAmount')" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="resolution" :label="$t('pages.reconciliation.resolution')" width="120" />
        <el-table-column :label="$t('common.actions')" width="280">
          <template #default="{ row }">
            <el-button v-if="row.resolution === 'PENDING'" link type="primary" @click="resolve(row, 'ADJUST_PLATFORM')">{{ $t('pages.reconciliation.adjustPlatform') }}</el-button>
            <el-button v-if="row.resolution === 'PENDING'" link @click="resolve(row, 'ADJUST_BANK')">{{ $t('pages.reconciliation.adjustBank') }}</el-button>
            <el-button v-if="row.resolution === 'PENDING'" link @click="resolve(row, 'IGNORED')">{{ $t('pages.reconciliation.ignore') }}</el-button>
            <el-button link type="primary" @click="$router.push('/adjustments')">{{ $t('pages.reconciliation.goAdjust') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else-if="tab === 'alerts'">
        <el-form :inline="true" :model="alertConfig" class="toolbar">
          <el-form-item :label="$t('pages.reconciliation.enabled')">
            <el-switch v-model="alertConfig.enabled" />
          </el-form-item>
          <el-form-item :label="$t('pages.reconciliation.webhook')">
            <el-input v-model="alertConfig.webhook_url" style="width: 280px" />
          </el-form-item>
          <el-form-item :label="$t('pages.reconciliation.email')">
            <el-input v-model="alertConfig.email" style="width: 200px" />
          </el-form-item>
          <el-button type="primary" @click="saveConfig">{{ $t('pages.reconciliation.saveConfig') }}</el-button>
        </el-form>
        <el-table :data="alerts" v-loading="loading">
          <el-table-column prop="title" :label="$t('pages.reconciliation.alertTitle')" min-width="180" />
          <el-table-column prop="batch_no" :label="$t('pages.reconciliation.batchNo')" min-width="140" />
          <el-table-column prop="severity" :label="$t('pages.reconciliation.severity')" width="110" />
          <el-table-column prop="channel" :label="$t('pages.reconciliation.channel')" width="110" />
          <el-table-column prop="status" :label="$t('common.status')" width="110" />
          <el-table-column prop="summary" :label="$t('pages.reconciliation.subtitle')" min-width="220" show-overflow-tooltip />
          <el-table-column :label="$t('common.actions')" width="120">
            <template #default="{ row }">
              <el-button v-if="row.status === 'OPEN'" link type="primary" @click="ack(row)">{{ $t('pages.reconciliation.ack') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-table v-else :data="checks" v-loading="loading">
        <el-table-column prop="account_no" :label="$t('pages.reconciliation.account')" min-width="140" />
        <el-table-column prop="platform_balance" :label="$t('pages.reconciliation.bookBalance')" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="bank_statement_balance" :label="$t('pages.reconciliation.bankBalance')" min-width="110" :formatter="formatMoneyCell" />
        <el-table-column prop="difference" :label="$t('pages.reconciliation.difference')" min-width="100" :formatter="formatMoneyCell" />
        <el-table-column prop="is_balanced" :label="$t('pages.reconciliation.balanced')" width="90" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/PageHeader.vue'
import {
  getReconBatches, getReconDiffs, getNostroChecks, resolveReconDiff,
  getReconAlerts, ackReconAlert, getReconAlertConfig, updateReconAlertConfig
} from '@/api/reconciliation'
import { unwrapList, formatMoneyCell } from '@/utils/format'

const { t } = useI18n()
const tab = ref('batches')
const loading = ref(false)
const batches = ref([])
const diffs = ref([])
const checks = ref([])
const alerts = ref([])
const alertConfig = reactive({ enabled: true, webhook_url: '', email: '' })

async function load() {
  loading.value = true
  try {
    if (tab.value === 'batches' || tab.value === 'results') batches.value = unwrapList(await getReconBatches({ page_size: 50 })).rows
    else if (tab.value === 'diffs') diffs.value = unwrapList(await getReconDiffs({ page_size: 50 })).rows
    else if (tab.value === 'alerts') {
      alerts.value = unwrapList(await getReconAlerts({ page_size: 50 })).rows
      const cfg = await getReconAlertConfig()
      alertConfig.enabled = cfg.enabled !== false
      alertConfig.webhook_url = cfg.webhook_url || ''
      alertConfig.email = cfg.email || ''
    }
    else checks.value = unwrapList(await getNostroChecks({ page_size: 50 })).rows
  } finally { loading.value = false }
}
async function resolve(row, resolution) {
  await resolveReconDiff(row.id, { resolution, resolved_by: 'admin', note: '' })
  ElMessage.success(t('pages.reconciliation.processed'))
  load()
}
async function ack(row) {
  await ackReconAlert(row.id, { acked_by: 'admin' })
  ElMessage.success(t('pages.reconciliation.acked'))
  load()
}
async function saveConfig() {
  await updateReconAlertConfig(alertConfig)
  ElMessage.success(t('pages.reconciliation.configSaved'))
}
onMounted(load)
</script>
