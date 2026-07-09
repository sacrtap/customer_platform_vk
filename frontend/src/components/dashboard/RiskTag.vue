<template>
  <StatusBadge :label="label" :type="mappedType" size="sm" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  label: string
  level?: 'high' | 'medium' | 'low'
}>()

const mappedType = computed(() => {
  switch (props.level) {
    case 'high':
      return 'danger'
    case 'medium':
      return 'warning'
    case 'low':
      return 'success'
    default:
      return 'success'
  }
})
</script>