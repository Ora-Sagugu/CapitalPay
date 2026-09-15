<template>
  <div class="page-header">
    <div>
      <h1>{{ displayTitle }}</h1>
      <p v-if="displaySubtitle">{{ displaySubtitle }}</p>
    </div>
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  titleKey: { type: String, default: '' },
  subtitleKey: { type: String, default: '' }
})

const route = useRoute()
const { t, te } = useI18n()

const displayTitle = computed(() => {
  const key = props.titleKey || route.meta?.titleKey
  if (key && te(key)) return t(key)
  return props.title
})
const displaySubtitle = computed(() => {
  if (props.subtitleKey && te(props.subtitleKey)) return t(props.subtitleKey)
  return props.subtitle
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}
.page-header p {
  margin: 4px 0 0;
  color: #8c8c8c;
  font-size: 13px;
}
</style>
