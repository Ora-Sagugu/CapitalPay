<template>
  <el-row :gutter="12" class="kpi-row">
    <el-col v-for="item in items" :key="item.label" :span="item.span || span">
      <div class="kpi-card">
        <div class="kpi-body">
          <div class="kpi-value">{{ item.value }}</div>
          <div class="kpi-label">{{ item.label }}</div>
          <div v-if="item.hint" class="kpi-hint">{{ item.hint }}</div>
        </div>
        <div v-if="item.icon" class="kpi-icon" :style="{ background: item.bg || '#fff3e8', color: item.color || '#f08040' }">
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
        </div>
      </div>
    </el-col>
  </el-row>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  span: { type: Number, default: 6 }
})
</script>

<style scoped>
.kpi-row { margin-bottom: 14px; }
.kpi-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  min-height: 88px;
}
.kpi-value { font-size: 26px; font-weight: 700; line-height: 1.2; }
.kpi-label { color: #8c8c8c; font-size: 13px; margin-top: 4px; }
.kpi-hint { color: #b0b0b0; font-size: 12px; margin-top: 2px; }
.kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
