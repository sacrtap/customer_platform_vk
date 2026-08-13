# 预测消费：单价配置可视化与预测参数控制 — 执行计划

## 实现顺序

### Phase A: 后端模型 + 配置接口（1 天）

1. **A1: 创建 ForecastUnitPrice 模型**
   - 文件：`backend/app/models/forecast_config.py`（新建）
   - 字段：device_type(PK), unit_price, updated_at
   - 生成 Alembic 迁移或直接创建表（开发环境直建）

2. **A2: 价格配置 API 路由**
   - 文件：`backend/app/routes/analytics.py`
   - 新增 `GET /consumption/price-config` 和 `PUT /consumption/price-config`
   - `PUT` 接收 `{"prices": {"L": 15.0, "N": 28.0, "X": 30.0}}`

3. **A3: 改造单价读取逻辑**
   - 文件：`backend/app/services/analytics.py`
   - 新增 `_get_unit_prices()` 方法（优先从表，回退到 config.py）
   - 替换所有 `get_settings().consumption_forecast_unit_prices` 调用

4. **A4: 预测参数扩展**
   - 文件：`backend/app/services/analytics.py`
   - `forecast_consumption` 增加 `apply_to`, `forecast_months`, `forecast_until` 参数
   - `get_forecast_trend` 增加 `forecast_months`, `forecast_until` 参数
   - 路由层新增参数解析

5. **A5: 缓存 key 更新**
   - 价格配置 TTL 60 秒，更新时清除预测缓存
   - 预测缓存 key 加入价格版本戳

### Phase B: 前端改造（1 天）

6. **B1: API 层更新**
   - 文件：`frontend/src/api/analytics.ts`
   - 新增 `getPriceConfig()`, `updatePriceConfig()`
   - 扩展 `getConsumptionForecast` 参数（apply_to, forecast_months, forecast_until）

7. **B2: 预测参数面板组件**
   - 文件：`frontend/src/views/analytics/Forecast.vue`
   - 新增单价编辑区域（L/N/X 三个输入框 + 保存按钮）
   - 新增预测范围选择（radio: all/future_only）
   - 新增月份数/截止月份选择

8. **B3: 页面逻辑适配**
   - 加载时读取价格配置并显示
   - 修改后调用 updatePriceConfig → 重新加载 forecast
   - 参数变化时自动刷新

### Phase C: 验证（0.5 天）

9. **C1: 后端测试**
   - 单元测试覆盖价格配置读写
   - 单元测试覆盖 `apply_to=future_only` 过滤逻辑
   - 单元测试覆盖 `forecast_months` 限制

10. **C2: 前端类型检查**
    - `pnpm type-check` 通过

11. **C3: 端到端验证**
    - 页面加载显示当前单价
    - 修改单价后重新预测结果变化
    - 切换"仅后续月份"后历史数据不变
    - 截止月份选择生效

## 验证命令

```bash
# 后端
cd backend && ruff check app/ && python -m pytest tests/test_analytics_service.py -k "Forecast or Price" -x -q

# 前端
cd frontend && pnpm type-check && pnpm build
```

## 风险文件

| 文件 | 风险 |
|------|------|
| `backend/app/services/analytics.py` | 单价读取替换影响所有预测路径 |
| `frontend/src/views/analytics/Forecast.vue` | 新增面板可能破坏布局 |
| 数据库迁移 | 需要创建新表，确保迁移脚本兼容性 |
