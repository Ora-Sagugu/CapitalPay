<template>
  <button class="chat-fab" type="button" title="Operations support" @click="onClick">
    <el-icon :size="22"><ChatDotRound /></el-icon>
  </button>
</template>

<script setup>
import { ElMessage } from 'element-plus'
function onClick() {
  ElMessage.info('The support channel is a demonstration. Contact operations.')
}
</script>
