# 客户详情页面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构客户详情页面，采用现代企业风格，新增数据可视化组件，提升用户体验和信息展示效率

**Architecture:** 保持现有 Tabs 布局结构，在每个 Tab 内优化视觉呈现，新增 4 个可视化组件（健康度仪表、消费等级进度条、余额趋势图、用量分布图），使用 ECharts 作为图表库

**Tech Stack:** Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + ECharts 5.4 + Python 3.12 + Sanic 22.12

---

## Phase 1: 后端 API 开发

### Task 1: 余额趋势 API - Service 层

**Files:**
- Modify: `backend/app/services/analytics.py`
- Test: `backend/tests/test_analytics_service.py`

- [ ] **Step 1: 编写余额趋势 Service 方法的测试**

```python
# 添加到 test_analytics_service.py
class TestBalanceTrendService:
    @pytest.mark.asyncio
    async def test_get_balance_trend_success(self, mock_db_session):
        """测试获取余额趋势成功场景"""
        from app.services.analytics import AnalyticsService
        from datetime import date
        
        service = AnalyticsService(mock_db_session)
        result = await service.get_balance_trend(
            customer_id=1,
            months=6
        )
        
        assert len(result) == 6
        assert all('month' in item for item in result)
        assert all('total_amount' in item for item in result)
        assert all('real_amount' in item for item in result)
        assert all('bonus_amount' in item for item in result)
    
    @pytest.mark.asyncio
    async def test_get_balance_trend_no_data(self, mock_db_session):
        """测试无余额数据时返回空列表"""
        from app.services.analytics import AnalyticsService
        
        service = AnalyticsService(mock_db_session)
        result = await service.get_balance_trend(customer_id=999, months=6)
        
        assert result == []
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_analytics_service.py::TestBalanceTrendService::test_get_balance_trend_success -v
```
Expected: FAIL with "AttributeError: 'AnalyticsService' object has no attribute 'get_balance_trend'"

- [ ] **Step 3: 编写最小实现**

在 `backend/app/services/analytics.py` 的 `AnalyticsService` 类中添加：

```python
async def get_balance_trend(
    self, customer_id: int, months: int = 6
) -> List[Dict[str, Any]]:
    """获取客户余额趋势（按月聚合）"""
    from datetime import timedelta
    from sqlalchemy import select, func, extract
    from app.models.billing import (
        CustomerBalance,
        RechargeRecord,
        ConsumptionRecord,
    )
    
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=months * 30)
    
    stmt = (
        select(
            extract('year', ConsumptionRecord.created_at).label('year'),
            extract('month', ConsumptionRecord.created_at).label('month'),
            func.sum(RechargeRecord.real_amount).label('total_recharge'),
            func.sum(ConsumptionRecord.amount).label('total_consumption'),
        )
        .select_from(ConsumptionRecord)
        .outerjoin(
            RechargeRecord,
            RechargeRecord.customer_id == ConsumptionRecord.customer_id,
        )
        .where(
            and_(
                ConsumptionRecord.customer_id == customer_id,
                ConsumptionRecord.created_at >= start_date,
                ConsumptionRecord.created_at <= end_date,
            )
        )
        .group_by(
            extract('year', ConsumptionRecord.created_at),
            extract('month', ConsumptionRecord.created_at),
        )
        .order_by(
            extract('year', ConsumptionRecord.created_at),
            extract('month', ConsumptionRecord.created_at),
        )
    )
    
    result = (await self.db.execute(stmt)).all()
    current_balance = await self._get_current_balance(customer_id)
    
    trend = []
    for row in result:
        trend.append({
            'month': f"{int(row.year)}-{int(row.month):02d}",
            'total_amount': 0,
            'real_amount': 0,
            'bonus_amount': 0,
        })
    
    if trend:
        trend[-1]['total_amount'] = current_balance.get('total_amount', 0)
        trend[-1]['real_amount'] = current_balance.get('real_amount', 0)
        trend[-1]['bonus_amount'] = current_balance.get('bonus_amount', 0)
    
    return trend

async def _get_current_balance(self, customer_id: int) -> Dict[str, float]:
    """获取客户当前余额"""
    from sqlalchemy import select
    from app.models.billing import CustomerBalance
    
    stmt = select(CustomerBalance).where(
        CustomerBalance.customer_id == customer_id,
        CustomerBalance.deleted_at.is_(None),
    )
    
    result = await self.db.execute(stmt)
    balance = result.scalars().first()
    
    if not balance:
        return {'total_amount': 0, 'real_amount': 0, 'bonus_amount': 0}
    
    return {
        'total_amount': float(balance.total_amount) if balance.total_amount else 0,
        'real_amount': float(balance.real_amount) if balance.real_amount else 0,
        'bonus_amount': float(balance.bonus_amount) if balance.bonus_amount else 0,
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_analytics_service.py::TestBalanceTrendService -v
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/services/analytics.py tests/test_analytics_service.py
git commit -m "feat: 添加余额趋势 Service 方法"
```

---

### Task 2: 余额趋势 API - Route 层

**Files:**
- Modify: `backend/app/routes/analytics.py`
- Test: `backend/tests/integration/test_analytics_api.py`

- [ ] **Step 1: 编写集成测试**

```python
class TestBalanceTrendApi:
    @pytest.mark.asyncio
    async def test_get_balance_trend_success(self, app, auth_headers, mock_db):
        request, response = await app.asgi_client.get(
            '/api/v1/analytics/billing/trend/1',
            headers=auth_headers,
            params={'months': 6}
        )
        assert response.status == 200
        data = response.json
        assert data['code'] == 0
        assert 'trend' in data['data']
```

- [ ] **Step 2: 运行测试验证失败** → 404

- [ ] **Step 3: 添加 API 路由**

```python
@analytics.route("/billing/trend/<customer_id:int>", methods=["GET"])
@auth_required
async def get_balance_trend(request: Request, customer_id: int):
    months = int(request.args.get("months", 6))
    months = min(months, 12)
    
    cache_key = f"{customer_id}:{months}"
    cached = await cache_service.get("analytics_balance_trend", cache_key)
    if cached is not None:
        return json(cached)
    
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)
    trend = await service.get_balance_trend(customer_id, months)
    
    result = {
        "code": 0,
        "message": "success",
        "data": {"customer_id": customer_id, "trend": trend},
    }
    await cache_service.set("analytics_balance_trend", result, cache_key)
    return json(result)
```

- [ ] **Step 4: 运行测试验证通过**

- [ ] **Step 5: 提交**

---

### Task 3: 客户健康度评分 API - Service 层

**Files:**
- Modify: `backend/app/services/analytics.py`
- Test: `backend/tests/test_analytics_service.py`

- [ ] **Step 1: 编写测试**

```python
class TestCustomerHealthScoreService:
    @pytest.mark.asyncio
    async def test_get_health_score_success(self, mock_db_session):
        from app.services.analytics import AnalyticsService
        service = AnalyticsService(mock_db_session)
        result = await service.get_customer_health_score(customer_id=1)
        
        assert 'health_score' in result
        assert 'health_level' in result
        assert 'components' in result
        assert 0 <= result['health_score'] <= 100
```

- [ ] **Step 2: 运行测试验证失败**

- [ ] **Step 3: 实现方法**

```python
async def get_customer_health_score(self, customer_id: int) -> Dict[str, Any]:
    """获取客户健康度评分
    
    健康度 = 用量达标率 × 50% + 余额充足率 × 30% + 回款及时率 × 20%
    """
    usage_rate = await self._calculate_usage_rate(customer_id)
    balance_rate = await self._calculate_balance_rate(customer_id)
    payment_rate = await self._calculate_payment_rate(customer_id)
    
    health_score = usage_rate * 0.5 + balance_rate * 0.3 + payment_rate * 0.2
    
    if health_score >= 80:
        health_level = '健康'
    elif health_score >= 60:
        health_level = '亚健康'
    else:
        health_level = '不健康'
    
    return {
        'health_score': round(health_score, 2),
        'health_level': health_level,
        'components': {
            'usage_rate': round(usage_rate, 2),
            'balance_rate': round(balance_rate, 2),
            'payment_rate': round(payment_rate, 2),
        },
        'weights': {'usage_rate': 0.5, 'balance_rate': 0.3, 'payment_rate': 0.2},
    }

async def _calculate_usage_rate(self, customer_id: int) -> float:
    # 近 3 个月实际用量 / 预期用量 (30000)
    # 返回 min(actual / 30000, 1.0) * 100
    ...

async def _calculate_balance_rate(self, customer_id: int) -> float:
    # 当前余额 / 月均消耗
    # 返回 min(current_balance / avg_monthly, 1.0) * 100
    ...

async def _calculate_payment_rate(self, customer_id: int) -> float:
    # 按时付款结算单数 / 总结算单数
    # 返回 (on_time / total) * 100
    ...
```

- [ ] **Step 4: 运行测试验证通过**

- [ ] **Step 5: 提交**

---

### Task 4: 客户健康度评分 API - Route 层

**Files:**
- Modify: `backend/app/routes/analytics.py`
- Test: `backend/tests/integration/test_analytics_api.py`

- [ ] **Step 1: 编写集成测试**

- [ ] **Step 2: 运行测试验证失败**

- [ ] **Step 3: 添加 API 路由**

```python
@analytics.route("/health/customers/<customer_id:int>/score", methods=["GET"])
@auth_required
async def get_customer_health_score(request: Request, customer_id: int):
    db_session = request.ctx.db_session
    service = AnalyticsService(db_session)
    result = await service.get_customer_health_score(customer_id)
    
    return json({
        "code": 0,
        "message": "success",
        "data": {"customer_id": customer_id, **result},
    })
```

- [ ] **Step 4: 运行测试验证通过**

- [ ] **Step 5: 提交**

---

## Phase 2: 前端组件开发

### Task 5: 安装 vue-echarts

**Files:** Modify `frontend/package.json`

- [ ] **Step 1: 安装**

```bash
cd frontend && npm install vue-echarts
```

- [ ] **Step 2: 验证**

```bash
npm list vue-echarts
```

- [ ] **Step 3: 提交**

---

### Task 6: 创建健康度仪表组件

**Files:** Create `frontend/src/components/charts/HealthGauge.vue`

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="health-gauge">
    <v-chart :option="chartOption" :auto-resize="true" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { PieChart } from 'echarts/charts'
// ... echarts 配置

const props = defineProps<{ score: number; level: string }>()

const chartOption = computed(() => ({
  series: [{
    type: 'pie',
    radius: ['75%', '100%'],
    data: [
      { value: props.score, itemStyle: { color: getHealthColor(props.score) } },
      { value: 100 - props.score, itemStyle: { color: '#f0f0f0' } },
    ],
    label: {
      show: true,
      position: 'center',
      formatter: `{score|${props.score}}`,
      rich: { score: { fontSize: 28, fontWeight: 'bold' } },
    },
  }],
}))

function getHealthColor(score: number): string {
  if (score >= 80) return '#22C55E'
  if (score >= 60) return '#F59E0B'
  return '#EF4444'
}
</script>
```

- [ ] **Step 2: 提交**

---

### Task 7: 创建消费等级进度条组件

**Files:** Create `frontend/src/components/ConsumeLevelProgress.vue`

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="consume-level-progress">
    <div class="level-info">
      <span>当前：{{ currentLevel }}</span>
      <span>下一级：{{ nextLevel }}</span>
    </div>
    <div class="progress-track">
      <div class="progress-bar" :style="{ width: progress + '%' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
const LEVELS = ['C', 'B', 'A', 'KA']
const COLORS = ['#F97316', '#3B82F6', '#22C55E', '#A855F7']

const props = defineProps<{ currentLevel: string; progress: number }>()
// ... 实现
</script>
```

- [ ] **Step 2: 提交**

---

### Task 8: 创建余额趋势图组件

**Files:** Create `frontend/src/components/charts/BalanceTrendChart.vue`

- [ ] **Step 1: 创建组件** - 多系列折线图

- [ ] **Step 2: 提交**

---

### Task 9: 创建用量分布图组件

**Files:** Create `frontend/src/components/charts/UsageDistributionChart.vue`

- [ ] **Step 1: 创建组件** - 环形图

- [ ] **Step 2: 提交**

---

### Task 10: 重构客户详情页面

**Files:** Modify `frontend/src/views/customers/Detail.vue`

- [ ] **Step 1: 导入新组件和 API**

- [ ] **Step 2: 添加 API 调用函数**

- [ ] **Step 3: 更新画像信息 Tab - 添加健康度仪表和消费等级进度条**

- [ ] **Step 4: 更新余额信息 Tab - 添加余额趋势图**

- [ ] **Step 5: 更新用量数据 Tab - 添加用量分布图**

- [ ] **Step 6: 运行类型检查**

```bash
cd frontend && npx vue-tsc --noEmit
```

- [ ] **Step 7: 提交**

---

## Phase 3: 测试与优化

### Task 11: 编写前端 E2E 测试

**Files:** Create `frontend/tests/e2e/customer-detail.spec.ts`

- [ ] **Step 1: 创建测试文件**

- [ ] **Step 2: 运行测试**

```bash
npm run test:e2e -- --grep "客户详情页面"
```

- [ ] **Step 3: 提交**

---

### Task 12: 视觉细节打磨

- [ ] 优化卡片 hover 动效
- [ ] 优化骨架屏加载动画
- [ ] 优化响应式布局
- [ ] 提交

---

### Task 13: 性能优化

- [ ] 添加数据缓存
- [ ] 优化图表渲染
- [ ] 提交

---

## 验收清单

- [ ] 后端单元测试通过 (coverage ≥ 50%)
- [ ] 后端集成测试通过
- [ ] 前端类型检查通过
- [ ] 前端 E2E 测试通过
- [ ] 健康度仪表正确显示
- [ ] 消费等级进度条正确显示
- [ ] 余额趋势图正确显示
- [ ] 用量分布图正确显示
- [ ] 响应式布局正常
- [ ] 动效流畅

---

**计划结束**
