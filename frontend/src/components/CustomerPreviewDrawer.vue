<template>
  <a-drawer
    :visible="visible"
    :width="400"
    :footer="false"
    placement="right"
    @cancel="$emit('update:visible', false)"
  >
    <template #title>客户 360 预览</template>
    <div v-if="data" class="drawer-content">
      <div class="drawer-customer-info">
        <span class="logo">{{ data.name?.charAt(0) }}</span>
        <div>
          <h4>{{ data.name }}</h4>
          <span class="subtle"
            >{{ data.industry }} · 规模 {{ data.scale_level }} · 消费 {{ data.consume_level }}</span
          >
        </div>
      </div>
      <div class="drawer-kpi-grid">
        <div class="drawer-kpi">
          <span>当前余额</span><b>{{ data.balance }}</b>
        </div>
        <div class="drawer-kpi">
          <span>30天消耗</span><b>{{ data.usage_30d }}</b>
        </div>
        <div class="drawer-kpi">
          <span>健康度</span><b :class="data.health_class">{{ data.health }}</b>
        </div>
        <div class="drawer-kpi">
          <span>预计耗尽</span><b class="danger">{{ data.forecast_days }}</b>
        </div>
      </div>
      <div v-if="data.recent_events?.length" class="drawer-section">
        <h5>最近操作</h5>
        <div class="drawer-timeline">
          <div v-for="event in data.recent_events" :key="event.time" class="drawer-event">
            <span>{{ event.time }}</span
            ><b>{{ event.action }}</b>
          </div>
        </div>
      </div>
      <div class="drawer-actions">
        <a-button type="primary" @click="goDetail">查看详情</a-button>
        <a-button>生成结算单</a-button>
        <a-button>提醒充值</a-button>
      </div>
    </div>
    <div v-else-if="loading" style="text-align: center; padding: 40px">
      <a-spin />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps<{ visible: boolean; customerId: number | null }>()
const emit = defineEmits<{ 'update:visible': [val: boolean] }>()
const router = useRouter()
const data = ref<Record<string, unknown> | null>(null)
const loading = ref(false)

watch(
  () => [props.customerId, props.visible],
  async ([id, vis]) => {
    if (id && vis) {
      loading.value = true
      data.value = null
      try {
        // TODO: 调用 customerApi.getSummary(id as number) 当后端端点就绪后
        // 目前使用模拟数据
        data.value = {
          name: '客户名称',
          industry: '房产',
          scale_level: 'A',
          consume_level: 'S',
          balance: '¥820,000',
          usage_30d: '¥482,000',
          health: '关注',
          health_class: 'amber',
          forecast_days: '5 天',
          recent_events: [
            { time: '今天 10:24', action: '生成 6 月结算单' },
            { time: '昨天 16:12', action: '余额预警已推送' },
          ],
        }
      } finally {
        loading.value = false
      }
    }
  },
  { immediate: true }
)

const goDetail = () => {
  emit('update:visible', false)
  if (props.customerId) {
    const resolved = router.resolve(`/customers/${props.customerId}`)
    window.open(resolved.href, '_blank')
  }
}
</script>

<style scoped>
.drawer-customer-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.drawer-customer-info .logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}
.drawer-customer-info h4 {
  margin: 0;
  font-size: 16px;
}
.drawer-kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.drawer-kpi {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
}
.drawer-kpi span {
  font-size: 12px;
  color: var(--muted);
  display: block;
}
.drawer-kpi b {
  font-size: 18px;
  font-weight: 800;
}
.drawer-section h5 {
  margin: 0 0 8px;
  font-size: 14px;
}
.drawer-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.drawer-event {
  display: flex;
  gap: 8px;
  font-size: 13px;
}
.drawer-event span {
  color: var(--muted);
  flex-shrink: 0;
}
.drawer-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.danger {
  color: #dc2626;
}
.amber {
  color: #d97706;
}
.green {
  color: #059669;
}
</style>
