# Analytics Consumption Forecast Spec

> 预测消费功能的技术契约。记录接口签名、算法口径、数据字段约定。

## Scope / Trigger

- 触发：预测消费页面 MVP 实现（替代旧"预测回款"）
- 关键决策：预测回款 → 预测消费；基于用量（order_count）× 单价矩阵估算
- 渐进式：数据 <3 月用保持，3-6 月滚动均值，6-12 月环比加权，≥12 月同比修正

## Signatures

### 后端 API（`backend/app/routes/analytics.py`）

```
GET /api/v1/analytics/consumption/forecast
  params: year, month?, keyword?, device_type?, force_refresh?, apply_to?, forecast_months?, forecast_until?

GET /api/v1/analytics/consumption/forecast-trend
  params: year, force_refresh?, apply_to?, forecast_months?, forecast_until?

GET /api/v1/analytics/consumption/price-config
  params: (none)

PUT /api/v1/analytics/consumption/price-config  (@require_permission("analytics:forecast"))
  body: {"prices": {"L": 14.5, "N": 30.0, "X": 30.0}}

GET /api/v1/analytics/consumption/data-readiness
  params: (none)

POST /api/v1/analytics/consumption/accuracy  (@require_permission("analytics:forecast"))
  params: (none) — 记录最新数据月预测准确度
```

### 服务方法（`backend/app/services/analytics.py`）

```python
async def forecast_consumption(year, month=None, customer_id=None, keyword=None, device_type=None, apply_to="all", forecast_months=None, forecast_until=None) -> List[Dict]
async def get_forecast_summary(year, month=None, customer_id=None, keyword=None, device_type=None, apply_to="all", forecast_months=None, forecast_until=None) -> Dict
async def get_forecast_trend(year, apply_to="all", forecast_months=None, forecast_until=None) -> List[Dict]
async def get_unit_prices() -> Dict[str, float]
async def update_unit_prices(prices: Dict[str, float]) -> None
async def get_data_readiness() -> Dict
async def record_prediction_accuracy() -> Dict
```

### 单价配置模型（`backend/app/models/forecast_config.py`）

```python
class ForecastUnitPrice(Base):  # 直接继承 Base，非 BaseModel
    __tablename__ = "forecast_unit_prices"
    device_type = Column(String(10), primary_key=True)  # L/N/X
    unit_price = Column(Numeric(10, 2))
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

- **表结构约定**：`device_type` 为自然主键，不继承 `BaseModel`（避免引入 `id`、`created_at`、`deleted_at` 三列）
- **何时用 BaseModel**：需要自增 id 主键 + 软删除的表才继承 `BaseModel`；以业务字段为 PK 的表应直接继承 `Base`
- **回退策略**：表为空时回退到 `config.py` 的 `consumption_forecast_unit_prices` 默认值

## Contracts

### 单价矩阵（`backend/app/config.py`）

```python
consumption_forecast_unit_prices: dict = {"L": 14.5, "N": 30.0, "X": 30.0}
```

- 用户提供的可靠全年均值（元/套）
- **勿用 `DailyConsumption.total_cost`** 校准单价——开发环境计费规则不可靠，该字段不可信
- 正确用量口径 = `order_count`（套数），非 `total_floor_count`（楼层）

### forecast 响应

```json
{
  "forecasts": [{
    "customer_id": 1, "company_id": "C001", "customer_name": "客户A",
    "device_type": "L",
    "estimated_usage": 100, "unit_price": 14.5, "forecast_amount": 1450.0,
    "forecast_method": "historical_hold|cold_start|trimmed",
    "is_active": true, "consume_level": "C1"
  }],
  "summary": {
    "total_forecast": 145000.0, "actual_this_month": 80043.0,
    "month_over_month_change": 5.2,
    "active_customer_count": 90, "total_customer_count": 2705,
    "confidence": "low|medium|high"
  }
}
```

### trend 响应

```json
[{
  "month": "2026-07", "actual": 80042.5, "forecast": 80042.5,
  "is_actual": true
}]
```

- `is_actual` **仅当该月 actual > 0** 时为 true（有真实数据才标实盘）
- 未来月份 forecast 统一用 `_estimate_future_consumption()`（活跃客户预测口径，与 summary.total_forecast 一致）
- ⚠️ 旧 `_estimate_month_consumption`（全部原始 order_count × 单价）与 summary 口径差 15 倍，已被移除——预测值必须口径统一

### data-readiness 响应

```json
{
  "months_with_data": 1, "total_months_target": 12,
  "customer_coverage_pct": 6.6, "confidence": "low",
  "earliest_data_month": "2026-07-01", "latest_data_month": "2026-07-31"
}
```

### accuracy 响应（POST /consumption/accuracy）

```json
{"recorded": true, "year": 2026, "month": 7,
 "forecast_total": 85874.0, "actual_total": 80042.5,
 "mape": 7.29, "deviation_pct": 7.29, "alert": false}
```

- 写入 `audit_logs`（action=`forecast_accuracy`, extra_metadata=JSON）
- `alert = deviation_pct > 30`

## Validation & Error Matrix

| Condition | Behavior |
|-----------|----------|
| 无消费数据（`_get_latest_usage_month` 返回 None） | forecast 返回 `[]`，readiness 返回 months=0/low |
| 冷启动客户（原始 order_count=0 且有消费等级） | 用同 device_type + consume_level 均值，method=cold_start |
| 离群（order_count > 3×同类型均值） | 截断到 3×均值，method=trimmed |
| 休眠客户（3 月无记录） | is_active=false，不纳入 total_forecast 但保留明细行 |
| 冷启动后又被截断 | method 仍为 cold_start（优先级：cold_start > trimmed > historical_hold） |

## Good/Base/Bad Cases

- Good: 活跃客户 L=100 套 → 100×14.5=1450, method=historical_hold, is_active=true
- Base: 冷启动客户 0 套 + consume_level=C2 → 用 L/C2 均值, method=cold_start
- Bad: 冷启动客户被误标为 trimmed（修复前 bug：用替换后的 orders 判断导致冷启动优先于截断丢失）

## Tests Required

- `tests/test_analytics_service.py`:
  - TestForecastConsumption: success（用量×单价）/ no_data / trimmed 截断
  - TestGetDataReadiness: no_data / one_month
  - TestGetForecastTrend: mixed（7月实盘+其他统一预测）/ no_data
- 断言点：forecast_method 优先级、estimated_usage、is_active、口径一致性（trend 未来月 = summary.total_forecast）

## Wrong vs Correct

### Wrong

```python
# 用替换后的 orders 判断 → 冷启动客户被标为 trimmed
if orders <= 0:
    method = "cold_start"
elif int(row.total_orders or 0) != orders:
    method = "trimmed"
```

### Correct

```python
# 用原始用量判断方法，cold_start 优先级最高
if used_cold_start:
    method = "cold_start"
elif original_orders > 0 and capped_orders != orders:
    method = "trimmed"
```

## 前端契约（`frontend/src/api/analytics.ts`）

```typescript
export interface ConsumptionForecast { ... forecast_method, is_active, estimated_usage, unit_price, forecast_amount ... }
export interface ForecastSummary { total_forecast, actual_this_month, month_over_month_change, active_customer_count, total_customer_count, confidence }
export interface ForecastTrendItem { month, actual: number|null, forecast, is_actual }
export interface DataReadiness { months_with_data, total_months_target, customer_coverage_pct, confidence, ... }
```

- 页面 `frontend/src/views/analytics/Forecast.vue`：标题"预测消费"，含数据就绪度横幅、置信度标签、趋势图（实盘/预测区分）、设备拆解图、明细表（方法+活跃标注）
- 侧边栏/布局：`AppSidebar.vue`、`useAppLayout.ts` 中"预测回款"→"预测消费"
- 旧接口 `/analytics/prediction/*` 保留兼容（旧函数 getMonthlyPrediction/getPredictionTrend 仍在）
