<template>
  <div class="page-card">
    <el-result icon="info" title="汇款申请" sub-title="客户门户暂不支持在线发起跨境汇款">
      <template #extra>
        <el-alert
          title="请通过以下渠道办理汇款"
          type="warning"
          :closable="false"
          style="max-width: 640px; text-align: left"
        >
          <ul style="margin: 8px 0 0; padding-left: 20px">
            <li>联系 Techtanium 运营人员代为录入汇款订单</li>
            <li>商户/代理通过 OpenAPI 调用 <code>/api/v1/payment/remittance/apply/</code> 发起汇款</li>
            <li>完成资料审核（资料完善）并绑定商户后，方可正常办理汇款业务</li>
          </ul>
        </el-alert>
        <div style="margin-top: 16px">
          <el-button type="primary" @click="$router.push('/onboarding')">去完善资料</el-button>
          <el-button @click="$router.push('/orders')">查看支付记录</el-button>
        </div>
      </template>
    </el-result>

    <el-divider />

    <h4 style="margin-top: 0">汇款信息参考（仅供填写备忘）</h4>
    <el-form :model="draft" label-width="120px" style="max-width: 640px" disabled>
      <el-form-item label="收款人姓名">
        <el-input v-model="draft.beneficiary_name" />
      </el-form-item>
      <el-form-item label="收款账号">
        <el-input v-model="draft.beneficiary_account" />
      </el-form-item>
      <el-form-item label="汇款金额">
        <el-input v-model="draft.amount" />
      </el-form-item>
      <el-form-item label="币种">
        <el-input v-model="draft.currency" />
      </el-form-item>
      <el-form-item label="汇款用途">
        <el-input v-model="draft.remittance_purpose" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <el-text type="info">以上表单为只读示意，实际汇款需通过运营后台或 OpenAPI 提交。</el-text>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const draft = reactive({
  beneficiary_name: '',
  beneficiary_account: '',
  amount: '',
  currency: 'USD',
  remittance_purpose: ''
})
</script>
