# Design — 健康度评估排除规则

## 边界

- 后端：`services/analytics.py` `get_customer_health_score`
- 前端：`api/analytics.ts`（CustomerHealthScore 类型）、`views/customers/detail/CustomerProfileTab.vue`、`components/charts/HealthGauge.vue`
- 不改：健康度分析页（`Health.vue` / `get_customer_health_stats` / 预警 / 未消耗列表）——独立逻辑

## 现状

- `Customer` 表无 `health_score` 字段，评分为实时计算，权重：用量达标率 50% + 余额充足率 30% + 回款及时率 20%。
- 后端返回 `{score, usage_rate, balance_rate, payment_rate, health_level}`。
- 前端类型 `CustomerHealthScore` 定义了 `score: number`、`level: string` 等，但实际后端返回
  `health_level` 而非 `level`（现存字段不一致：前端 `HealthGauge :level="healthScore.level"` 恒为
  undefined）。本次顺带修正前端类型（`level` 改为可选并映射 `health_level`）或在
  `CustomerProfileTab.vue` 使用 `healthScore.health_level`，二选一，实现时确认最小改动路径。

## 排除规则

命中以下任一条件 → 不参与评估，返回「不适用」语义：

1. `Customer.is_settlement_enabled == False`
2. `Customer.account_type == '客户测试账号'`
3. `Customer.account_type == '内部账号'`

注意：`is_settlement_enabled` 为 `nullable=True, default=True`，NULL 视为启用结算
（不排除），用 `is_(False)` 判断，避免 NULL 语义偏差。

## 后端实现

`get_customer_health_score` 开头新增客户查询与排除判断：

```python
customer_stmt = select(Customer).where(
    Customer.id == customer_id,
    Customer.deleted_at.is_(None),
)
customer = (await self.db.execute(customer_stmt)).scalar_one_or_none()
if customer is None:
    raise ValueError(...)  # 或沿用路由层 404 校验

excluded = (
    customer.is_settlement_enabled is False
    or customer.account_type in ("客户测试账号", "内部账号")
)
if excluded:
    return {
        "score": None,
        "usage_rate": None,
        "balance_rate": None,
        "payment_rate": None,
        "health_level": "not_applicable",
    }
```

（`get_customer_health_score` 现有实现内部已引用 Customer 类，需确认 import 位置；
路由层已有客户存在性校验，Service 层以 `scalar_one_or_none` 兜底。）

## 前端实现

1. `api/analytics.ts` `CustomerHealthScore`：
   - `score: number | null`
   - `health_level: string` 保留；`level` 字段按现状修正/移除（与实现确认）
2. `CustomerProfileTab.vue`：
   - `healthScore.score == null` 时展示「不参与评估」文案（替换 HealthGauge 仪表盘）
   - 处理 `healthScore == null`（无数据）保持现状
3. `HealthGauge.vue`：不修改（score 为 null 时由父组件分支处理，不渲染仪表盘）

## 展示设计

```vue
<div v-else class="chart-content">
  <HealthGauge
    v-if="healthScore && healthScore.score != null"
    :score="healthScore.score"
    :level="healthScore.health_level"
  />
  <div v-else-if="healthScore && healthScore.score === null" class="chart-na">
    该客户不参与健康度评估
  </div>
</div>
```

## 兼容性

- 响应结构新增 null 值语义，`score` 从 `number` 变为 `number | null`，前端有配套处理。
- 健康度分析页不消费此接口，无影响。
- 无数据库改动、无迁移。
