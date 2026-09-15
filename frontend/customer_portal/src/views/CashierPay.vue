<template>
  <div class="cashier">
    <div class="card">
      <h1>{{ $t('cashier.title') }}</h1>
      <p class="sub">{{ $t('cashier.sub') }}</p>
      <el-descriptions v-if="order.order_no" :column="1" border>
        <el-descriptions-item :label="$t('cashier.orderNo')">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item :label="$t('cashier.merchant')">{{ order.merchant_name }}</el-descriptions-item>
        <el-descriptions-item :label="$t('cashier.amount')">{{ money(order.amount) }} {{ order.currency }}</el-descriptions-item>
        <el-descriptions-item :label="$t('cashier.fee')">{{ money(order.fee_amount) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('cashier.method')">{{ order.pay_method }}</el-descriptions-item>
        <el-descriptions-item :label="$t('cashier.status')">{{ order.status }}</el-descriptions-item>
        <el-descriptions-item label="UIN">{{ order.unique_identification_no }}</el-descriptions-item>
      </el-descriptions>
      <div class="actions">
        <el-button v-if="order.pay_method === 'WIRE_TRANSFER'" type="primary" disabled>{{ $t('cashier.wire') }}</el-button>
        <el-button v-else type="primary" :disabled="order.status !== 'PENDING_PAY' && order.status !== 'PRE_CREATE'" @click="pay">{{ $t('cashier.pay') }}</el-button>
      </div>
    </div>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getCashierOrder, payCashierOrder } from '@/api/payments'
import { money } from '@/utils/format'

const { t } = useI18n()

const route = useRoute()
const order = ref({})
async function load() {
  order.value = await getCashierOrder(route.params.orderNo, route.query.uin)
}
async function pay() {
  const data = await payCashierOrder(route.params.orderNo, { uin: route.query.uin || order.value.unique_identification_no })
  ElMessage.success(t('cashier.success') + data.status)
  load()
}
onMounted(load)
</script>
<style scoped>
.cashier { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f2ee; }
.card { width: 480px; background: #fff; padding: 28px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.06); }
h1 { margin: 0 0 4px; }
.sub { color: #888; margin: 0 0 16px; }
.actions { margin-top: 20px; text-align: right; }
</style>
