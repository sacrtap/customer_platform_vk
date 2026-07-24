# Phase 1: P0 核心页面全栈重构 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 Home、客户列表、客户详情、消耗分析、结算管理（余额/计费/结算单）7 个 P0 页面，实现视觉统一 + 交互增强 + 后端 API 调整。

**Architecture:** 使用 Phase 0 创建的通用组件（PageHeader/FilterSection/TableSection/ChartCard/BatchToolbar/QuickFilterTags）重构页面布局；实现重构优化计划中的交互功能；后端新增/扩展 API 端点支持新功能。

**Tech Stack:** Vue 3 + Arco Design + TypeScript + ECharts + Vite + Vitest + Playwright | FastAPI + SQLAlchemy + Python 3.12

## Global Constraints

- 文件修改前必须先读取（项目硬规则）
- 所有后端修改操作在 `async with db_session.begin():` 块内
- 所有 API 端点添加 `@auth_required` 装饰器
- 余额扣款使用行级锁（`FOR UPDATE`）
- Python 3.12.x，不支持 3.13+
- CI 测试覆盖率 ≥ 50%
- 思考过程及会话内回复必须使用中文
- pre-commit 脚本使用 `$BACKEND_DIR/.venv/bin/python`

## File Structure

**前端修改（已有文件）：**
- `frontend/src/views/Home.vue` — 运营工作台
- `frontend/src/views/customers/Index.vue` — 客户列表
- `frontend/src/views/customers/components/CustomerTable.vue` — 客户表格
- `frontend/src/views/customers/components/CustomerFilters.vue` — 客户筛选
- `frontend/src/views/customers/Detail.vue` — 客户详情
- `frontend/src/views/customers/detail/*.vue` — 详情 Tab 组件
- `frontend/src/views/analytics/Consumption.vue` — 消耗分析
- `frontend/src/views/billing/Balance.vue` — 余额管理
- `frontend/src/views/billing/PricingRules.vue` — 计费规则
- `frontend/src/views/billing/Invoices.vue` — 结算单管理
- `frontend/src/views/billing/components/*.vue` — 结算子组件

**前端新建：**
- `frontend/src/components/SyncStatusBar.vue` — 同步状态条
- `frontend/src/components/Sparkline.vue` — 迷你折线图
- `frontend/src/components/CustomerPreviewDrawer.vue` — 客户 360 预览抽屉

**后端修改：**
- `backend/app/routes/analytics.py` — 扩展趋势接口 + 消耗分析接口
- `backend/app/routes/sync_tasks.py` — 新增同步状态端点
- `backend/app/routes/customers.py` — 新增 summary/saved-views/related/balance-forecast
- `backend/app/routes/billing.py` — 新增余额趋势/预警阈值/批量充值等端点

---

### Task 1: 运营工作台 — 视觉重构 + 同步状态条

**Files:**
- Modify: `frontend/src/views/Home.vue`
- Create: `frontend/src/components/SyncStatusBar.vue`

**Interfaces:**
- Consumes: `PageHeader`, `.kpi-strip`, `.mini`, `.hero`, `ChartCard` (Phase 0 组件)
- Produces: `SyncStatusBar` 组件，含 `status`/`lastSync`/`nextSync` props + `#action` slot

- [ ] **Step 1: 创建 SyncStatusBar 组件**

创建 `frontend/src/components/SyncStatusBar.vue`：

```vue
<template>
  <div class="sync-status-bar" :class="status">
    <span class="pulse-dot" />
    <span class="sync-text">
      <template v-if="status === 'ok'">数据同步正常</template>
      <template v-else-if="status === 'warning'">数据同步异常 · {{ warningText }}</template>
      <template v-else>同步中…</template>
      · 最近同步 {{ lastSync }}<template v-if="nextSync"> · 下次同步 {{ nextSync }}</template>
    </span>
    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  status: 'ok' | 'warning' | 'syncing'
  lastSync: string
  nextSync?: string
  warningText?: string
}>()
</script>

<style scoped>
.sync-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 14px;
}
.sync-status-bar.ok {
  background: rgba(16, 185, 129, .08);
  color: #059669;
}
.sync-status-bar.warning {
  background: rgba(245, 158, 11, .08);
  color: #D97706;
}
.sync-status-bar.syncing {
  background: rgba(29, 78, 216, .08);
  color: #1D4ED8;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 2s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.sync-text { flex: 1; }
</style>
```

- [ ] **Step 2: 读取当前 Home.vue**

Read: `frontend/src/views/Home.vue`

- [ ] **Step 3: 重构 Home.vue 模板**

将 `.headline` 替换为 `PageHeader`，添加 `SyncStatusBar`，KPI 卡片使用 `.kpi-strip` + `.mini` + `@click` 下钻：

```vue
<template>
  <div class="page-content">
    <PageHeader eyebrow="Home" title="运营工作台"
      subtitle="首屏回答三个问题：今天经营是否正常、哪些客户需要处理、同步/结算链路是否有风险。">
      <template #actions>
        <a-button @click="saveView">保存视图</a-button>
        <a-button type="primary" @click="createSyncTask">新建同步任务</a-button>
      </template>
    </PageHeader>

    <SyncStatusBar status="ok" lastSync="10:00" nextSync="11:00">
      <template #action>
        <a-button size="mini" @click="$router.push('/system/sync-logs')">查看日志</a-button>
      </template>
    </SyncStatusBar>

    <div class="kpi-strip">
      <div class="mini kpi-clickable" @click="$router.push('/customers')">
        <span>活跃客户</span><b>{{ kpiData.activeCustomers }}</b>
        <span class="up">较上月 +{{ kpiData.customerGrowth }}%</span>
      </div>
      <div class="mini kpi-clickable" @click="$router.push('/analytics/consumption')">
        <span>本月消耗</span><b>{{ kpiData.monthlyConsumption }}</b>
        <span class="up">完成 {{ kpiData.consumptionRate }}%</span>
      </div>
      <div class="mini kpi-clickable" @click="$router.push('/analytics/payment')">
        <span>待回款</span><b>{{ kpiData.pendingPayment }}</b>
        <span class="warn">{{ kpiData.expiringInvoices }} 单临期</span>
      </div>
      <div class="mini kpi-clickable" @click="$router.push('/billing/balances')">
        <span>低余额客户</span><b>{{ kpiData.lowBalanceCount }}</b>
        <span class="down">需跟进</span>
      </div>
      <div class="mini kpi-clickable" @click="$router.push('/system/sync-logs')">
        <span>同步成功率</span><b>{{ kpiData.syncRate }}%</b>
        <span class="up">稳定</span>
      </div>
      <div class="mini kpi-clickable" @click="$router.push('/system/sync-logs')">
        <span>异常任务</span><b>{{ kpiData.errorTasks }}</b>
        <span class="warn">待重试</span>
      </div>
    </div>

    <div class="hero" style="margin-top:14px">
      <ChartCard title="经营趋势">
        <template #actions>
          <div class="tabs">
            <span v-for="tab in trendTabs" :key="tab.key"
              class="tab" :class="{ active: activeTrendTab === tab.key }"
              @click="activeTrendTab = tab.key">{{ tab.label }}</span>
          </div>
        </template>
        <div ref="trendChartRef" style="height: 260px" />
      </ChartCard>
      <ChartCard title="异常与待办">
        <template #actions>
          <span class="tag amber">{{ todoList.length }} 项</span>
          <label class="toggle-switch">
            <input type="checkbox" v-model="sortByAmount">
            <span class="toggle-label-text">按金额排序</span>
          </label>
        </template>
        <div class="compact-list">
          <div v-for="item in sortedTodoList" :key="item.label" class="row">
            <span>{{ item.label }}</span><b>{{ item.count }}</b>
          </div>
        </div>
        <div class="quick-actions">
          <button class="quick-action-btn" @click="$router.push('/customers')"><span class="qa-icon">+</span>新建客户</button>
          <button class="quick-action-btn" @click="$router.push('/billing/invoices')"><span class="qa-icon">¥</span>生成结算单</button>
          <button class="quick-action-btn" @click="$router.push('/system/sync-logs')"><span class="qa-icon">⟳</span>数据同步</button>
          <button class="quick-action-btn" @click="exportReport"><span class="qa-icon">↓</span>导出报告</button>
        </div>
      </ChartCard>
    </div>

    <div class="card pad" style="margin-top:14px">
      <div class="section-title">
        <h2>今日优先跟进客户</h2>
        <a-button @click="batchAssign">批量分配</a-button>
      </div>
      <a-table :data="priorityCustomers" :pagination="false" size="small">
        <a-table-column title="客户" data-index="name" />
        <a-table-column title="健康度" data-index="health">
          <template #cell="{ record }">
            <span class="tag" :class="record.healthClass">{{ record.health }}</span>
          </template>
        </a-table-column>
        <a-table-column title="本月消耗" data-index="consumption" />
        <a-table-column title="余额可用" data-index="balanceDays" />
        <a-table-column title="风险" data-index="risk" />
        <a-table-column title="负责人" data-index="manager" />
        <a-table-column title="下一步">
          <template #cell="{ record }">
            <a-dropdown @select="(val) => handleAction(val, record)">
              <a-button size="mini">操作 ▾</a-button>
              <template #content>
                <a-doption value="detail">查看详情</a-doption>
                <a-doption value="recharge">提醒充值</a-doption>
                <a-doption value="invoice">生成结算单</a-doption>
                <a-doption value="assign">分配负责人</a-doption>
              </template>
            </a-dropdown>
          </template>
        </a-table-column>
      </a-table>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 实现 Home.vue 脚本逻辑**

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import ChartCard from '@/components/ChartCard.vue'
import SyncStatusBar from '@/components/SyncStatusBar.vue'
import { Message } from '@arco-design/web-vue'

const kpiData = ref({
  activeCustomers: '1,248',
  customerGrowth: '8.4',
  monthlyConsumption: '¥8.42M',
  consumptionRate: '73',
  pendingPayment: '¥1.36M',
  expiringInvoices: '18',
  lowBalanceCount: '42',
  syncRate: '98.6',
  errorTasks: '7',
})

const trendTabs = [
  { key: 'consume', label: '消耗' },
  { key: 'payment', label: '回款' },
  { key: 'customers', label: '客户数' },
  { key: 'health', label: '健康度' },
]
const activeTrendTab = ref('consume')
const trendChartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const todoList = ref([
  { label: '余额低于 7 天', count: 42, amount: 420000, urgency: 5 },
  { label: '结算单生成失败', count: 5, amount: 860000, urgency: 3 },
  { label: '同步任务待重试', count: 7, amount: 120000, urgency: 7 },
  { label: '长期未消耗客户', count: 16, amount: 2400000, urgency: 2 },
  { label: '权限变更待审核', count: 3, amount: 0, urgency: 1 },
])
const sortByAmount = ref(false)
const sortedTodoList = computed(() => {
  const list = [...todoList.value]
  return sortByAmount.value ? list.sort((a, b) => b.amount - a.amount) : list.sort((a, b) => b.urgency - a.urgency)
})

const priorityCustomers = ref([
  { id: 1, name: '万科华东', health: '关注', healthClass: 'amber', consumption: '¥482,000', balanceDays: '5 天', risk: '余额不足', manager: '王明' },
  { id: 2, name: '绿城服务', health: '高风险', healthClass: 'red', consumption: '¥196,000', balanceDays: '2 天', risk: '结算失败', manager: '李娜' },
  { id: 3, name: '龙湖集团', health: '健康', healthClass: 'green', consumption: '¥711,000', balanceDays: '18 天', risk: '无', manager: '陈涛' },
])

const renderChart = () => {
  if (!trendChartRef.value) return
  if (!chart) chart = echarts.init(trendChartRef.value)
  chart.setOption({
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: ['1日','5日','10日','15日','20日','25日','30日'] },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#E2E8F0' } } },
    series: [{
      type: 'line',
      smooth: true,
      data: [120, 135, 128, 142, 138, 155, 168],
      areaStyle: { color: 'rgba(29,78,216,.08)' },
      lineStyle: { color: '#1D4ED8', width: 2 },
      itemStyle: { color: '#1D4ED8' },
    }],
  })
}

watch(activeTrendTab, () => renderChart())

const saveView = () => Message.info('保存视图功能开发中')
const createSyncTask = () => Message.info('新建同步任务功能开发中')
const exportReport = () => Message.info('导出报告功能开发中')
const batchAssign = () => Message.info('批量分配功能开发中')

const handleAction = (val: string, record: any) => {
  if (val === 'detail') router.push(`/customers/${record.id}`)
  else Message.info(`${val} - ${record.name}`)
}

onMounted(() => {
  nextTick(() => renderChart())
  window.addEventListener('resize', () => chart?.resize())
})
</script>
```

- [ ] **Step 5: 补充 Home.vue 样式**

```vue
<style scoped>
.kpi-clickable { cursor: pointer; transition: all .18s ease; }
.kpi-clickable:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.quick-actions {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 12px;
}
.quick-action-btn {
  border: 1px solid var(--line); background: var(--bg); border-radius: 10px;
  padding: 10px; display: flex; align-items: center; justify-content: center; gap: 6px;
  cursor: pointer; font-size: 13px; color: var(--muted); transition: all .18s ease;
}
.quick-action-btn:hover { border-color: #93C5FD; color: var(--primary); background: #EFF6FF; }
.qa-icon { font-size: 16px; font-weight: 700; }
.tabs { display: flex; gap: 4px; }
.tab { padding: 4px 10px; border-radius: 999px; font-size: 12px; color: var(--muted); cursor: pointer; }
.tab.active { background: #DBEAFE; color: #1D4ED8; font-weight: 600; }
.tag { font-size: 12px; padding: 2px 8px; border-radius: 999px; }
.tag.amber { background: #FEF3C7; color: #D97706; }
.tag.red { background: #FEE2E2; color: #DC2626; }
.tag.green { background: #DCFCE7; color: #059669; }
</style>
```

- [ ] **Step 6: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/Home.vue frontend/src/components/SyncStatusBar.vue
git commit -m "feat: refactor Home page with PageHeader, SyncStatusBar, KPI drill-down, trend chart tabs"
```

---

### Task 2: 后端 — 同步状态端点 + 趋势接口扩展

**Files:**
- Modify: `backend/app/routes/sync_tasks.py`
- Modify: `backend/app/routes/analytics.py`

**Interfaces:**
- Produces: `GET /api/sync/status` 返回同步状态、`GET /api/analytics/trend?metric=xxx` 支持多指标

- [ ] **Step 1: 读取现有文件**

Read: `backend/app/routes/sync_tasks.py`
Read: `backend/app/routes/analytics.py`

- [ ] **Step 2: 在 sync_tasks.py 添加 GET /api/sync/status**

在 `sync_tasks.py` 中添加：

```python
@router.get("/sync/status")
@auth_required
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    """获取同步状态摘要"""
    # 查询最近同步任务
    result = await db.execute(
        select(SyncTask)
        .order_by(SyncTask.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    # 统计异常任务数
    error_count = await db.scalar(
        select(func.count(SyncTask.id)).where(SyncTask.status == "failed")
    )

    # 今日成功率
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_total = await db.scalar(
        select(func.count(SyncTask.id)).where(SyncTask.created_at >= today_start)
    )
    today_success = await db.scalar(
        select(func.count(SyncTask.id)).where(
            SyncTask.created_at >= today_start,
            SyncTask.status == "success"
        )
    )
    rate = round(today_success / today_total * 100, 1) if today_total > 0 else 0

    return {
        "status": "ok" if error_count == 0 else "warning",
        "last_sync": latest.created_at.strftime("%H:%M") if latest else None,
        "next_sync": None,  # 可从定时任务配置获取
        "sync_rate": rate,
        "error_count": error_count or 0,
    }
```

- [ ] **Step 3: 在 analytics.py 扩展趋势接口**

在 `analytics.py` 中找到趋势接口，添加 `metric` 参数：

```python
@router.get("/analytics/trend")
@auth_required
async def get_trend(
    metric: str = "consumption",  # consumption | payment | customer_count | health
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """获取趋势数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    if metric == "consumption":
        # 查询每日消耗
        result = await db.execute(
            select(
                func.date(UsageRecord.created_at).label("date"),
                func.sum(UsageRecord.amount).label("value"),
            )
            .where(UsageRecord.created_at >= start_date)
            .group_by(func.date(UsageRecord.created_at))
            .order_by(func.date(UsageRecord.created_at))
        )
    elif metric == "payment":
        result = await db.execute(
            select(
                func.date(Invoice.created_at).label("date"),
                func.sum(Invoice.amount).label("value"),
            )
            .where(Invoice.created_at >= start_date)
            .group_by(func.date(Invoice.created_at))
            .order_by(func.date(Invoice.created_at))
        )
    elif metric == "customer_count":
        result = await db.execute(
            select(
                func.date(Customer.created_at).label("date"),
                func.count(Customer.id).label("value"),
            )
            .where(Customer.created_at >= start_date)
            .group_by(func.date(Customer.created_at))
            .order_by(func.date(Customer.created_at))
        )
    elif metric == "health":
        result = await db.execute(
            select(
                func.date(HealthRecord.created_at).label("date"),
                func.avg(HealthRecord.score).label("value"),
            )
            .where(HealthRecord.created_at >= start_date)
            .group_by(func.date(HealthRecord.created_at))
            .order_by(func.date(HealthRecord.created_at))
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid metric parameter")

    rows = result.all()
    return {
        "dates": [r.date for r in rows],
        "values": [float(r.value) for r in rows],
    }
```

- [ ] **Step 4: 写测试**

创建 `backend/tests/unit/test_sync_status.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_sync_status_returns_ok():
    """测试同步状态端点返回正确格式"""
    # 模拟数据库
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.scalar = AsyncMock(side_effect=[0, 0, 0])

    result = await get_sync_status(db=mock_db)
    assert result["status"] == "ok"
    assert "last_sync" in result
    assert "sync_rate" in result
    assert "error_count" in result
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_sync_status.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routes/sync_tasks.py backend/app/routes/analytics.py backend/tests/unit/test_sync_status.py
git commit -m "feat: add sync status endpoint and extend trend API with metric parameter"
```

---

### Task 3: 客户列表 — 视觉重构 + KPI 联动 + 预览抽屉

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`
- Modify: `frontend/src/views/customers/components/CustomerTable.vue`
- Modify: `frontend/src/views/customers/components/CustomerFilters.vue`
- Create: `frontend/src/components/CustomerPreviewDrawer.vue`

**Interfaces:**
- Consumes: `PageHeader`, `FilterSection`, `TableSection`, `BatchToolbar`, `QuickFilterTags`
- Produces: `CustomerPreviewDrawer` 组件，含 `customerId` prop + `visible` v-model

- [ ] **Step 1: 创建 CustomerPreviewDrawer 组件**

创建 `frontend/src/components/CustomerPreviewDrawer.vue`：

```vue
<template>
  <a-drawer :visible="visible" @update:visible="$emit('update:visible', $event)"
    :width="400" :footer="false" placement="right">
    <template #title>客户 360 预览</template>
    <div v-if="data" class="drawer-content">
      <div class="drawer-customer-info">
        <span class="logo">{{ data.name?.charAt(0) }}</span>
        <div>
          <h4>{{ data.name }}</h4>
          <span class="subtle">{{ data.industry }} · 规模 {{ data.scale_level }} · 消费 {{ data.consume_level }}</span>
        </div>
      </div>
      <div class="drawer-kpi-grid">
        <div class="drawer-kpi"><span>当前余额</span><b>{{ data.balance }}</b></div>
        <div class="drawer-kpi"><span>30天消耗</span><b>{{ data.usage_30d }}</b></div>
        <div class="drawer-kpi"><span>健康度</span><b :class="data.health_class">{{ data.health }}</b></div>
        <div class="drawer-kpi"><span>预计耗尽</span><b class="danger">{{ data.forecast_days }}</b></div>
      </div>
      <div class="drawer-section">
        <h5>最近操作</h5>
        <div class="drawer-timeline">
          <div v-for="event in data.recent_events" :key="event.time" class="drawer-event">
            <span>{{ event.time }}</span><b>{{ event.action }}</b>
          </div>
        </div>
      </div>
      <div class="drawer-actions">
        <a-button type="primary" @click="goDetail">查看详情</a-button>
        <a-button>生成结算单</a-button>
        <a-button>提醒充值</a-button>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { customerApi } from '@/api'

const props = defineProps<{ visible: boolean; customerId: number | null }>()
const emit = defineEmits<{ 'update:visible': [val: boolean] }>()
const router = useRouter()
const data = ref<any>(null)

watch(() => props.customerId, async (id) => {
  if (id && props.visible) {
    const res = await customerApi.getSummary(id)
    data.value = res.data
  }
}, { immediate: true })

const goDetail = () => {
  emit('update:visible', false)
  if (props.customerId) router.push(`/customers/${props.customerId}`)
}
</script>

<style scoped>
.drawer-customer-info { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.drawer-customer-info .logo {
  width: 40px; height: 40px; border-radius: 12px; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  background: #DBEAFE; color: #1D4ED8; font-weight: 700;
}
.drawer-customer-info h4 { margin: 0; font-size: 16px; }
.drawer-kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
.drawer-kpi { padding: 10px; border: 1px solid var(--line); border-radius: 10px; }
.drawer-kpi span { font-size: 12px; color: var(--muted); display: block; }
.drawer-kpi b { font-size: 18px; font-weight: 800; }
.drawer-section h5 { margin: 0 0 8px; font-size: 14px; }
.drawer-timeline { display: flex; flex-direction: column; gap: 8px; }
.drawer-event { display: flex; gap: 8px; font-size: 13px; }
.drawer-event span { color: var(--muted); flex-shrink: 0; }
.drawer-actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.danger { color: #DC2626; }
.amber { color: #D97706; }
</style>
```

- [ ] **Step 2: 读取现有文件**

Read: `frontend/src/views/customers/Index.vue`
Read: `frontend/src/views/customers/components/CustomerTable.vue`
Read: `frontend/src/views/customers/components/CustomerFilters.vue`

- [ ] **Step 3: 重构 Index.vue 使用通用组件**

将 `Index.vue` 的模板重构为使用 `PageHeader` + `FilterSection` + `TableSection` + `BatchToolbar`，添加 KPI 联动筛选和预览抽屉。关键变更：
- 替换 `.headline` → `PageHeader`
- 替换 `.card.pad` 筛选区 → `FilterSection`
- KPI 卡片添加 `@click` → 设置筛选条件
- 表格行添加 `@click` → 打开预览抽屉
- 引入 `CustomerPreviewDrawer`

- [ ] **Step 4: 在 CustomerTable.vue 添加行 hover 预览交互**

- [ ] **Step 5: 在 CustomerFilters.vue 添加保存视图功能入口**

- [ ] **Step 6: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/customers/ frontend/src/components/CustomerPreviewDrawer.vue
git commit -m "feat: refactor customer list with PageHeader, KPI filter, preview drawer"
```

---

### Task 4: 后端 — 客户摘要 + 保存视图 + 关联客户 + 余额预测

**Files:**
- Modify: `backend/app/routes/customers.py`

**Interfaces:**
- Produces: `GET /api/customers/:id/summary`, `POST/GET /api/customers/saved-views`, `GET /api/customers/:id/related`, `GET /api/customers/:id/balance-forecast`

- [ ] **Step 1: 读取现有文件**

Read: `backend/app/routes/customers.py`

- [ ] **Step 2: 添加 GET /api/customers/:id/summary**

```python
@router.get("/customers/{customer_id}/summary")
@auth_required
async def get_customer_summary(customer_id: int, db: AsyncSession = Depends(get_db)):
    """客户 360 预览数据"""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 30天消耗
    thirty_days_ago = datetime.now() - timedelta(days=30)
    usage = await db.scalar(
        select(func.sum(UsageRecord.amount))
        .where(UsageRecord.customer_id == customer_id, UsageRecord.created_at >= thirty_days_ago)
    )

    # 健康度
    health = await db.scalar(
        select(HealthRecord.score)
        .where(HealthRecord.customer_id == customer_id)
        .order_by(HealthRecord.created_at.desc())
    )

    # 余额耗尽预测
    daily_usage = (usage or 0) / 30
    forecast_days = int(customer.balance / daily_usage) if daily_usage > 0 else None

    # 最近操作
    events_result = await db.execute(
        select(OperationLog)
        .where(OperationLog.customer_id == customer_id)
        .order_by(OperationLog.created_at.desc())
        .limit(5)
    )

    return {
        "name": customer.name,
        "industry": customer.industry_type,
        "scale_level": customer.scale_level,
        "consume_level": customer.consume_level,
        "balance": f"¥{customer.balance:,.0f}",
        "usage_30d": f"¥{usage or 0:,.0f}",
        "health": _health_label(health),
        "health_class": _health_class(health),
        "forecast_days": f"{forecast_days} 天" if forecast_days else "安全",
        "recent_events": [
            {"time": e.created_at.strftime("%m-%d %H:%M"), "action": e.action}
            for e in events_result.scalars()
        ],
    }
```

- [ ] **Step 3: 添加 GET /api/customers/:id/related**

```python
@router.get("/customers/{customer_id}/related")
@auth_required
async def get_related_customers(customer_id: int, db: AsyncSession = Depends(get_db)):
    """关联客户推荐（同行业同规模）"""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    result = await db.execute(
        select(Customer)
        .where(
            Customer.id != customer_id,
            Customer.industry_type == customer.industry_type,
            Customer.scale_level == customer.scale_level,
        )
        .limit(4)
    )
    return [
        {"id": c.id, "name": c.name, "industry": c.industry_type,
         "scale_level": c.scale_level, "health": _health_label(c.health_score)}
        for c in result.scalars()
    ]
```

- [ ] **Step 4: 添加 GET /api/customers/:id/balance-forecast**

```python
@router.get("/customers/{customer_id}/balance-forecast")
@auth_required
async def get_balance_forecast(customer_id: int, db: AsyncSession = Depends(get_db)):
    """余额耗尽预测"""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    thirty_days_ago = datetime.now() - timedelta(days=30)
    usage = await db.scalar(
        select(func.sum(UsageRecord.amount))
        .where(UsageRecord.customer_id == customer_id, UsageRecord.created_at >= thirty_days_ago)
    )

    daily_avg = (usage or 0) / 30
    if daily_avg > 0:
        days_left = int(customer.balance / daily_avg)
        return {"days_left": days_left, "daily_avg": daily_avg, "status": "warning" if days_left <= 7 else "ok"}
    return {"days_left": None, "daily_avg": 0, "status": "safe"}
```

- [ ] **Step 5: 添加 POST/GET /api/customers/saved-views**

```python
@router.get("/customers/saved-views")
@auth_required
async def get_saved_views(db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    result = await db.execute(
        select(SavedView).where(SavedView.user_id == current_user.id).order_by(SavedView.updated_at.desc())
    )
    return [{"id": v.id, "name": v.name, "filters": v.filters} for v in result.scalars()]

@router.post("/customers/saved-views")
@auth_required
async def save_view(data: dict, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    view = SavedView(name=data["name"], filters=data["filters"], user_id=current_user.id)
    async with db.begin():
        db.add(view)
    return {"id": view.id, "name": view.name}
```

- [ ] **Step 6: 写测试**

创建 `backend/tests/unit/test_customer_endpoints.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_customer_summary():
    """测试客户摘要端点"""
    mock_db = AsyncMock()
    mock_customer = MagicMock()
    mock_customer.name = "万科华东"
    mock_customer.industry_type = "房产"
    mock_customer.scale_level = "A"
    mock_customer.consume_level = "S"
    mock_customer.balance = 820000
    mock_customer.health_score = 78
    mock_db.get = AsyncMock(return_value=mock_customer)
    mock_db.scalar = AsyncMock(side_effect=[482000, 78, None])
    mock_db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=[])))

    result = await get_customer_summary(customer_id=1, db=mock_db)
    assert result["name"] == "万科华东"
    assert "balance" in result
    assert "usage_30d" in result
```

- [ ] **Step 7: 运行测试**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_customer_endpoints.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/routes/customers.py backend/tests/unit/test_customer_endpoints.py
git commit -m "feat: add customer summary, related, balance-forecast, saved-views endpoints"
```

---

### Task 5: 客户详情 — Tab 导航 + 快捷操作栏 + 余额预测

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue`
- Modify: `frontend/src/views/customers/detail/*.vue` (6 个 Tab 组件)

**Interfaces:**
- Consumes: `PageHeader`, `ChartCard`, `SyncStatusBar`(复用), `CustomerPreviewDrawer`
- Produces: 详情页 6 Tab 导航 + 快捷操作栏 + 余额耗尽预测卡片

- [ ] **Step 1: 读取现有 Detail.vue**

Read: `frontend/src/views/customers/Detail.vue`

- [ ] **Step 2: 重构 Detail.vue**

关键变更：
- 替换 `.headline` → `PageHeader`
- 添加快捷操作栏（充值/结算单/编辑画像/提醒）
- KPI 卡片添加余额耗尽预测 + sparkline
- 6 个 Tab 导航对齐药丸标签样式
- URL hash 同步 Tab 切换

- [ ] **Step 3: 在画像 Tab 中添加健康度仪表盘**

- [ ] **Step 4: 在画像 Tab 中添加关联客户推荐**

- [ ] **Step 5: 在余额 Tab 中添加余额趋势 chart + 耗尽预测**

- [ ] **Step 6: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/customers/
git commit -m "feat: refactor customer detail with tab navigation, quick actions, balance forecast"
```

---

### Task 6: 消耗分析 — 视觉重构 + 同步提示 + 图表联动

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 1: 读取现有 Consumption.vue**

Read: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 2: 重构模板**

关键变更：
- 替换 `.headline` → `PageHeader`
- 添加 `SyncStatusBar`（同步质量提示）
- `.grid-4` → `.kpi-strip` + `.mini`
- SVG 占位图表替换为 ECharts 组件
- 环形图扇区 `@click` 联动 Top 排行表筛选
- 添加同比对比 Toggle（双线模式）
- 添加图表解释 `?` tooltip
- Top 排行表行 `@click` 跳转客户详情

- [ ] **Step 3: 实现 ECharts 趋势图**

- [ ] **Step 4: 实现 ECharts 环形图 + 联动**

- [ ] **Step 5: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/analytics/Consumption.vue
git commit -m "feat: refactor consumption analysis with sync notice, ECharts, chart-table linkage"
```

---

### Task 7: 后端 — 消耗分析接口扩展

**Files:**
- Modify: `backend/app/routes/analytics.py`

- [ ] **Step 1: 扩展消耗分析接口支持 compare 参数**

- [ ] **Step 2: 新增 GET /api/analytics/consumption/export**

- [ ] **Step 3: 返回数据中包含异常标记字段**

- [ ] **Step 4: 写测试并运行**

- [ ] **Step 5: 提交**

```bash
git add backend/app/routes/analytics.py backend/tests/unit/test_analytics_consumption.py
git commit -m "feat: extend consumption analytics API with compare, export, anomaly detection"
```

---

### Task 8: 余额管理 — 视觉重构 + Sparkline + 预测列 + 低余额高亮

**Files:**
- Create: `frontend/src/components/Sparkline.vue`
- Modify: `frontend/src/views/billing/Balance.vue`

- [ ] **Step 1: 创建 Sparkline 组件**

创建 `frontend/src/components/Sparkline.vue`：

```vue
<template>
  <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`">
    <polyline :points="points" fill="none" :stroke="color" stroke-width="1.5" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  data: number[]
  width?: number
  height?: number
  color?: string
}>(), {
  width: 50,
  height: 16,
  color: '#059669',
})

const points = computed(() => {
  if (!props.data.length) return ''
  const max = Math.max(...props.data)
  const min = Math.min(...props.data)
  const range = max - min || 1
  return props.data.map((v, i) => {
    const x = (i / (props.data.length - 1)) * props.width
    const y = props.height - ((v - min) / range) * (props.height - 2) - 1
    return `${x},${y}`
  }).join(' ')
})
</script>
```

- [ ] **Step 2: 读取现有 Balance.vue**

Read: `frontend/src/views/billing/Balance.vue`

- [ ] **Step 3: 重构模板**

关键变更：
- 替换 `.headline` → `PageHeader`
- KPI 卡片对齐 `.mini`
- 表格添加 Sparkline 列
- 添加"预计耗尽"列（标签样式）
- 低余额行 `row-warning` 高亮
- `BatchToolbar` 批量充值

- [ ] **Step 4: 验证构建并提交**

```bash
git add frontend/src/components/Sparkline.vue frontend/src/views/billing/Balance.vue
git commit -m "feat: refactor balance page with Sparkline, forecast column, low-balance highlight"
```

---

### Task 9: 计费规则 — 视觉重构 + 预览 + 冲突检测

**Files:**
- Modify: `frontend/src/views/billing/PricingRules.vue`

- [ ] **Step 1: 读取现有 PricingRules.vue**

- [ ] **Step 2: 重构模板**

关键变更：
- 替换 `.headline` → `PageHeader`
- `FilterSection` + `TableSection`
- 即将到期规则琥珀色高亮
- 冲突检测可视化列

- [ ] **Step 3: 验证构建并提交**

```bash
git add frontend/src/views/billing/PricingRules.vue
git commit -m "feat: refactor pricing rules with PageHeader, conflict detection, expiry highlight"
```

---

### Task 10: 结算单管理 — 视觉重构 + 生命周期 + 批量操作 + 快速筛选

**Files:**
- Modify: `frontend/src/views/billing/Invoices.vue`
- Modify: `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`

- [ ] **Step 1: 读取现有 Invoices.vue**

- [ ] **Step 2: 重构模板**

关键变更：
- 替换 `.headline` → `PageHeader`
- `QuickFilterTags`（待确认/逾期/本月新增）
- 逾期行红色高亮 + 倒计时
- 金额汇总页脚行
- 批量操作（确认/导出）
- `InvoiceDetailDrawer` 对齐样式

- [ ] **Step 3: 验证构建并提交**

```bash
git add frontend/src/views/billing/Invoices.vue frontend/src/views/billing/components/InvoiceDetailDrawer.vue
git commit -m "feat: refactor invoices with QuickFilterTags, lifecycle, batch ops, summary footer"
```

---

### Task 11: 后端 — 结算管理 API 扩展

**Files:**
- Modify: `backend/app/routes/billing.py`

- [ ] **Step 1: 读取现有 billing.py**

- [ ] **Step 2: 添加端点**

- `GET /api/billing/balances/:id/trend` — 余额趋势
- `POST /api/billing/balance-thresholds` — 预警阈值配置
- `POST /api/billing/balances/batch-recharge` — 批量充值（`FOR UPDATE` 行级锁）
- `POST /api/billing/pricing-rules/preview` — 规则生效预览
- `GET /api/billing/pricing-rules/:id/history` — 规则版本历史
- `POST /api/billing/invoices/batch` — 批量操作
- 所有端点添加 `@auth_required`

- [ ] **Step 3: 写测试**

- [ ] **Step 4: 运行测试**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_endpoints.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routes/billing.py backend/tests/unit/test_billing_endpoints.py
git commit -m "feat: add billing API endpoints for trends, thresholds, batch recharge, preview, history"
```

---

### Task 12: Phase 1 最终验证

- [ ] **Step 1: 验证前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 2: 验证类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: 运行后端测试**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/ -v --tb=short`
Expected: 所有测试通过

- [ ] **Step 4: 验证后端覆盖率**

Run: `cd backend && .venv/bin/python -m pytest --cov=app --cov-fail-under=50`
Expected: 覆盖率 ≥ 50%

- [ ] **Step 5: 运行前端单元测试**

Run: `cd frontend && npx vitest run src/components/__tests__/`
Expected: 所有组件测试通过

- [ ] **Step 6: 标记 Phase 1 完成**

更新 progress ledger 并提交。
