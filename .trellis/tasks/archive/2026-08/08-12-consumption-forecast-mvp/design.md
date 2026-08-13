# 预测消费页面 — 技术设计

## Architecture

### 数据流

```
DailyConsumption.order_count  (按客户×设备类型聚合)
        │
        ▼
┌─────────────────────────────────────┐
│         预测算法引擎                  │
│  (backend/services/analytics.py)    │
│                                     │
│  1. 取最近完整月用量（保持基线）       │
│  2. 新客户→消费等级中位数冷启动       │
│  3. trimmed 5% + 3 倍截断离群        │
│  4. 活跃度判断（3 月）               │
│  5. 单价矩阵 → 预测消费              │
│  6. 置信度计算                       │
└──────────────────┬──────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│         后端接口层                    │
│  (backend/app/routes/analytics.py)  │
│                                     │
│  GET /analytics/consumption/forecast     │
│  GET /analytics/consumption/forecast-trend  │
│  GET /analytics/consumption/data-readiness  │
└──────────────────┬──────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│         前端 Forecast.vue           │
│  (frontend/src/views/analytics/     │
│   Forecast.vue / ForecastNew.vue)   │
│                                     │
│  统计卡 · 趋势图 · 设备拆解 · 明细表  │
│  数据就绪度横幅 · 置信度标签 · 方法标注 │
└─────────────────────────────────────┘
```

### 后端接口设计

#### 1. `GET /analytics/consumption/forecast`

**改造自** `GET /analytics/prediction/monthly`

**参数**: `year`, `month`(可选), `keyword`(可选), `device_type`(可选), `force_refresh`(可选)

**返回**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "forecasts": [
      {
        "customer_id": 1,
        "company_id": "C001",
        "customer_name": "客户A",
        "device_type": "L",
        "estimated_usage": 100,          // 估算用量（order_count）
        "unit_price": 14.5,              // 单价
        "forecast_amount": 1450.0,       // 预测消费金额
        "forecast_method": "historical_hold",  // historical_hold/cold_start/trimmed
        "is_active": true,               // 是否活跃
        "consumption_level": "high"      // 消费等级（冷启动分层用）
      }
    ],
    "summary": {
      "total_forecast": 145000.0,
      "actual_this_month": 80043.0,
      "month_over_month_change": 5.2,
      "active_customer_count": 90,
      "total_customer_count": 2705,
      "confidence": "low"                // low/medium/high
    }
  }
}
```

#### 2. `GET /analytics/consumption/forecast-trend`

**改造自** `GET /analytics/prediction/trend`

**参数**: `year`, `force_refresh`(可选)

**返回**:
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "month": "2026-07",
      "actual": 80043.0,      // 已发生实盘（null 如果未来）
      "forecast": 145000.0,   // 预测值
      "is_actual": true       // 前端判断实心/虚线
    }
  ]
}
```

#### 3. `GET /analytics/consumption/data-readiness`

**新增**

**参数**: 无

**返回**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "months_with_data": 1,          // 有数据的月份数
    "total_months_target": 12,      // 目标月份数
    "customer_coverage_pct": 3.6,   // 有消费数据客户占比
    "confidence": "low",
    "earliest_data_month": "2026-07",
    "latest_data_month": "2026-07"
  }
}
```

### 算法设计

#### 预测消费引擎（`AnalyticsService.forecast_consumption`）

```python
async def forecast_consumption(self, year, month, customer_id, keyword, device_type):
    """预测消费主引擎"""

    # 1. 确定预测月份
    #    如果 month 指定 → 预测该月（历史月份用实际，未来月份用预测）
    #    如果 month 未指定 → 预测全年（已过月份用实际，未来月份用预测）

    # 2. 获取用量基线
    #    - 取最近完整月（当前最新数据月）的 order_count 按客户×设备类型聚合
    #    - 如果数据量 ≥ 3 个月 → 滚动均值
    #    - 如果数据量 ≥ 6 个月 → 环比加权
    #    - 如果数据量 ≥ 12 个月 → 同比修正

    # 3. 冷启动（新客户无历史）
    #    - 查询同设备类型 + 同消费等级客户的中位数 order_count
    #    - 从 CustomerProfile.consumption_level 获取等级

    # 4. 离群处理
    #    - 计算所有活跃客户 order_count 的 5%-95% 分位数
    #    - 超出 3 倍历史均值的客户截断到 3 倍

    # 5. 活跃度判断
    #    - 最近 3 个月有消费记录 = active
    #    - 否则标记为 inactive，不纳入总量

    # 6. 单价矩阵应用
    #    - 从配置表或配置文件读取单价
    #    - 预测消费 = estimated_usage × unit_price

    # 7. 置信度计算
    #    - months_with_data < 3 → low
    #    - 3-11 → medium
    #    - ≥12 → high
```

#### 单价矩阵配置

**方案：配置文件**（MVP 阶段，不建表）

在 `backend/app/config.py` 或 `backend/app/consumption_forecast.py` 新增：

```python
# 消费预测单价矩阵（元/套）
CONSUMPTION_FORECAST_UNIT_PRICES = {
    "L": 14.5,
    "N": 30.0,
    "X": 30.0,
}
```

用户后续可通过修改配置文件或将来建配置表来调整。

#### 准确度追踪

**方案**：在 `backend/app/services/analytics.py` 的预测流程中，每月结束时（或每次预测时）记录准确度信息：

```python
# 预测准确度日志（记录到文件或简单日志表）
# 格式：{year, month, total_forecast, total_actual, mape, record_date}
# 存储位置：用现有 sync_task_logs 或新建 prediction_accuracy 表
```

**MVP 简化**：写入现有日志系统（`audit_logs` 或 `sync_task_logs`），不新建表。后续迭代再建专用表。

### 前端改造

#### 改造方案

**Forecast.vue** 保留现有文件，进行以下改造：

1. **命名替换**：所有"预测回款"→"预测消费"，"回款"→"消费"
2. **API 调用**：从 `getMonthlyPrediction`/`getPredictionTrend` 改为新的消费预测接口
3. **字段映射**：`predicted_amount` → `forecast_amount`，新增 `forecast_method`、`is_active`、`unit_price`、`estimated_usage`
4. **趋势图**：`predicted` → `forecast`，新增 `is_actual` 判断渲染样式
5. **新增数据就绪度横幅**：调用 `data-readiness` 接口展示
6. **新增置信度标签**：从 summary 获取 `confidence` 字段渲染
7. **新增设备类型拆解图**：按 `device_type` 聚合 `forecast_amount` 显示饼图
8. **新增方法标注列**：`forecast_method` 映射为中文标签
9. **新增活跃标记列**：`is_active` 显示为活跃/休眠标签

#### 前端组件改造清单

| 组件 | 改动 |
|------|------|
| `Forecast.vue` | 核心改造（见上） |
| `api/analytics.ts` | 新增 `getConsumptionForecast`, `getConsumptionForecastTrend`, `getDataReadiness` |
| `AppSidebar.vue` | "预测回款" → "预测消费" |
| `useAppLayout.ts` | `key: 'forecast', label: '预测回款'` → `'预测消费'` |

### 缓存策略

- 预测结果缓存：TTL 30 分钟（复用 `cache_ttl_analytics_prediction: 1800`）
- data-readiness 缓存：TTL 1 小时
- 缓存清除时机：同步任务完成时清除 `analytics_prediction` 类别缓存
- 强制刷新：`force_refresh=true` 参数跳过缓存

### 兼容性

- 旧接口 `GET /analytics/prediction/monthly` 和 `GET /analytics/prediction/trend` 保留，返回重定向或兼容数据
- 旧路由 `/analytics/forecast` 保持不变（前端路由不变，后端 API 路径变）
- 旧字段名 `predicted_amount` 在新接口中改为 `forecast_amount`，不兼容

### 风险

- 同步任务完整性（假完成 bug）未修复 → 活跃度判断不可靠
- 7 月单月数据非稳态 → 预测基准偏差，横幅和置信度标签诚实标注
