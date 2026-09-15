<template>
  <div>
    <PageHeader
      title="Remittance Fee"
      subtitle="Every remittance is charged as a fixed fee plus a percentage of the principal, capped at the maximum."
    >
      <el-button @click="load">Refresh</el-button>
      <el-button type="primary" @click="save">Save</el-button>
    </PageHeader>
    <div class="page-card" v-loading="loading">
      <el-form :model="form" label-width="140px" style="max-width: 480px">
        <el-form-item label="Fixed fee">
          <el-input v-model="form.fixed_fee" />
        </el-form-item>
        <el-form-item label="Percent (%)">
          <el-input
            v-model="form.percent_rate"
            @blur="form.percent_rate = formatPercent(form.percent_rate)"
          />
        </el-form-item>
        <el-form-item label="Maximum fee">
          <el-input v-model="form.max_fee" />
        </el-form-item>
        <el-form-item label="Preview">
          <el-input :model-value="previewLabel" disabled />
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import { getRemittanceFeeConfig, updateRemittanceFeeConfig } from '@/api/param'
import { money } from '@/utils/format'

const loading = ref(false)
const form = reactive({
  fixed_fee: '0.00',
  percent_rate: '0.00',
  max_fee: '0.00'
})

function formatPercent(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0.00'
  return n.toFixed(2)
}

function previewFee() {
  const fixed = Number(form.fixed_fee)
  const percent = Number(form.percent_rate)
  const maxFee = Number(form.max_fee)
  if (![fixed, percent, maxFee].every(Number.isFinite)) return null
  const raw = fixed + 1000 * (percent / 100)
  return Math.min(raw, maxFee)
}

const previewLabel = computed(() => {
  const fee = previewFee()
  if (fee == null) return 'Enter valid amounts to preview a 1,000 remittance'
  return `On a remittance of 1,000 the charge is ${money(fee)}`
})

async function load() {
  loading.value = true
  try {
    const data = await getRemittanceFeeConfig()
    form.fixed_fee = data.fixed_fee
    form.percent_rate = formatPercent(data.percent_rate)
    form.max_fee = data.max_fee
  } finally {
    loading.value = false
  }
}

async function save() {
  form.percent_rate = formatPercent(form.percent_rate)
  await updateRemittanceFeeConfig({
    fixed_fee: form.fixed_fee,
    percent_rate: form.percent_rate,
    max_fee: form.max_fee
  })
  ElMessage.success('The record has been saved.')
  load()
}

onMounted(load)
</script>
