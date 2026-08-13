# 预测消费：单价配置可视化与预测参数控制 — 技术设计

## Architecture

### 数据流（新增部分）

```
[前端] 编辑单价 → PUT /price-config → 写入 forecast_unit_prices 表
[前端] 选择范围 → GET /forecast?apply_to=future_only&forecast_months=6 → 限定返回
[后端] 预测算法 → 从 forecast_unit_prices 表读取单价（替代 config.py 硬编码）
```

### 新增模型

**`backend/app/models/forecast_config.py`**:

```python
class ForecastUnitPrice(BaseModel):
    __tablename__ = "forecast_unit_prices"
    device_type = Column(String(10), primary_key=True)  # L/N/X
    unit_price = Column(Numeric(10, 2), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

### 后端接口

#### 1. `GET /api/v1/analytics/consumption/price-config`

返回当前单价配置：

```json
{
  "code": 0,
  "data": [
    {"device_type": "L", "unit_price": 14.5},
    {"device_type": "N", "unit_price": 30.0},
    {"device_type": "X", "unit_price": 30.0}
  ]
}
```

#### 2. `PUT /api/v1/analytics/consumption/price-config`

更新单价（全量替换）：

```json
// Request
{"prices": {"L": 15.0, "N": 28.0, "X": 30.0}}
// Response
{"code": 0, "message": "success", "data": {"prices": {...}}}
```

#### 3. `GET /api/v1/analytics/consumption/forecast`（改造）

**新增参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `apply_to` | string | `all` | `all` 更新历史及后续 / `future_only` 仅后续月份 |
| `forecast_months` | int | 12 | 预测月份数（1-24） |
| `forecast_until` | string | — | 截止月份 `YYYY-MM`，与 forecast_months 互斥 |

**逻辑变化**：

- 单价读取：从 `forecast_unit_prices` 表读取，表为空时回退到 `config.py` 默认值
- `apply_to=future_only`：预测结果只返回月份 >= 当前月的数据
- `forecast_months`：限制趋势图和明细表返回的月份数
- 缓存 key 加入价格版本号，避免修改后命中旧缓存

#### 4. `GET /api/v1/analytics/consumption/forecast-trend`（改造）

**新增参数**：`forecast_months`, `forecast_until`

**逻辑变化**：趋势图只返回指定范围内的月份。

### 单价读取策略

```python
async def _get_unit_prices(self) -> dict:
    """读取单价：优先从配置表，回退到 config.py 默认值"""
    stmt = select(ForecastUnitPrice)
    result = (await self.db.execute(stmt)).scalars().all()
    if result:
        return {row.device_type: float(row.unit_price) for row in result}
    # 回退到 config.py
    return get_settings().consumption_forecast_unit_prices
```

### 缓存策略

- 价格配置缓存 TTL 60 秒（或写时清除）
- 预测结果缓存 key 加入价格版本戳（`updated_at` 时间戳），修改单价后旧缓存自动失效

### 前端改造

**Forecast.vue 新增区域**：

```
┌──────────────────────────────────────────────┐
│  [预测参数面板]  (可折叠/展开)                 │
│  ┌──────────────────────────────────────────┐ │
│  │  单价配置:  L: [14.5]  N: [30.0]  X: [30.0]│ │
│  │  [重新预测]  [重置为默认值]                 │ │
│  │                                            │ │
│  │  预测范围: ● 更新历史及后续  ○ 仅后续月份    │ │
│  │  预测月数:  [12] 个月 或 截止: [2026-12]   │ │
│  └──────────────────────────────────────────┘ │
├──────────────────────────────────────────────┤
│  [原有统计卡片/图表/明细表]                    │
└──────────────────────────────────────────────┘
```

**关键交互**：
- 修改单价后，"重新预测"按钮高亮
- 点击"重新预测" → 调 `PUT /price-config` → 调 `GET /forecast` 刷新
- 预测范围/月数改变 → 自动重新加载（或点击"查询"）

### 兼容性

- 旧接口 URL 不变，新增参数带默认值（`apply_to=all, forecast_months=12`）
- 页面未配置单价时，显示从 config.py 读取的默认值
- 现有 `api/analytics.ts` 的函数签名需要扩展新参数
