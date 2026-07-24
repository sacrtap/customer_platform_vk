<template>
  <div class="grid-4">
    <KpiCard
      label="客户总数"
      :value="data.total"
      :trend="`本月新增 ${data.newThisMonth}`"
      trend-type="up"
      :active="active === 'all'"
      @click="emit('kpiChange', 'all')"
    />
    <KpiCard
      label="重点客户"
      :value="data.keyCustomers"
      :trend="`消耗贡献 ${data.keyContribution}%`"
      trend-type="neutral"
      :active="active === 'key'"
      @click="emit('kpiChange', 'key')"
    />
    <KpiCard
      label="待完善画像"
      :value="data.incompleteProfile"
      trend="影响分析准确性"
      trend-type="warn"
      :active="active === 'incomplete'"
      @click="emit('kpiChange', 'incomplete')"
    />
    <KpiCard
      label="我的客户"
      :value="data.myCustomers"
      trend="需运营跟进"
      trend-type="down"
      :active="active === 'mine'"
      @click="emit('kpiChange', 'mine')"
    />
  </div>
</template>

<script setup lang="ts">
import KpiCard from '@/components/ui/KpiCard.vue'

defineProps<{
  data: {
    total: string
    newThisMonth: number
    keyCustomers: number
    keyContribution: number
    incompleteProfile: number
    myCustomers: number
  }
  active: 'all' | 'key' | 'incomplete' | 'mine'
}>()

const emit = defineEmits<{
  kpiChange: [type: 'all' | 'key' | 'incomplete' | 'mine']
}>()
</script>
