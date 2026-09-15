<template>
  <div class="empty">
    <div class="icon">{{ icon }}</div>
    <div class="msg">{{ message }}</div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: 'No records available' },
  icon: { type: String, default: '📭' }
})
</script>

<style scoped>
.empty {
  padding: 56px 16px;
  text-align: center;
  color: #9aa0a6;
}
.icon { font-size: 48px; margin-bottom: 12px; }
.msg { font-size: 14px; }
</style>
