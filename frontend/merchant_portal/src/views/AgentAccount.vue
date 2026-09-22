<template>
  <div>
    <h1 class="ptitle">{{ $t('agent.accountTitle') }}</h1>
    <p class="psub">{{ $t('agent.earningsSub') }}</p>
    <AgentEarnings embedded />
  </div>
</template>

<script setup>
import AgentEarnings from './AgentEarnings.vue'
</script>

<style scoped>
.ptitle { margin: 0 0 4px; font-size: 22px; }
.psub { margin: 0 0 16px; color: #8c8c8c; font-size: 13px; }
</style>
