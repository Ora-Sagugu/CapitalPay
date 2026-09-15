<template>
  <div>
    <PageHeader title="Risk Rating" subtitle="Default Single Limit and Daily Count for each risk rating. Daily Limit is calculated as Single Limit × Daily Count." />
    <div class="page-card">
      <div class="toolbar">
        <el-button @click="load">Refresh</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column label="Risk Rating" min-width="140">
          <template #default="{ row }">{{ labels[row.risk_level] || row.risk_level }}</template>
        </el-table-column>
        <el-table-column label="Single Limit" min-width="140">
          <template #default="{ row }">{{ money(row.max_single_amount) }}</template>
        </el-table-column>
        <el-table-column prop="daily_count" label="Daily Count" min-width="130" />
        <el-table-column label="Daily Limit" min-width="140">
          <template #default="{ row }">{{ money(dailyLimit(row)) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="visible" :title="dialogTitle" width="480px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Single Limit"><el-input v-model="form.max_single_amount" /></el-form-item>
        <el-form-item label="Daily Count"><el-input v-model="form.daily_count" /></el-form-item>
        <el-form-item label="Daily Limit">
          <el-input :model-value="computedDailyLimit" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getRiskRatingLimits, updateRiskRatingLimit } from '@/api/param'
import { money, unwrapList } from '@/utils/format'

function dailyLimit(row) {
  const single = Number(row?.max_single_amount)
  const count = Number(row?.daily_count)
  if (!Number.isFinite(single) || !Number.isFinite(count)) return 0
  return single * count
}

const labels = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  BLOCKED: 'Blocked'
}

const rows = ref([])
const loading = ref(false)
const visible = ref(false)
const form = reactive({ id: '', risk_level: '', max_single_amount: '', daily_count: '' })

const computedDailyLimit = computed(() => money(dailyLimit(form)))

const dialogTitle = computed(() => {
  const name = labels[form.risk_level] || form.risk_level
  return name ? `Edit ${name}` : 'Edit Risk Rating'
})

async function load() {
  loading.value = true
  try {
    const data = await getRiskRatingLimits()
    rows.value = unwrapList(data).rows
  } finally {
    loading.value = false
  }
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    risk_level: row.risk_level,
    max_single_amount: row.max_single_amount,
    daily_count: row.daily_count
  })
  visible.value = true
}

async function save() {
  await updateRiskRatingLimit(form.id, {
    max_single_amount: form.max_single_amount,
    daily_count: form.daily_count === '' ? 0 : Number(form.daily_count)
  })
  ElMessage.success('The record has been saved.')
  visible.value = false
  load()
}

onMounted(load)
</script>
