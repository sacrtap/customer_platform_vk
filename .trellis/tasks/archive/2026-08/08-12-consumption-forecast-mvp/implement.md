# 预测消费页面 MVP — 执行计划

## 实现顺序

### Phase A: 后端算法 + 接口（3 天）

1. **A1: 单价矩阵配置**
   - 文件：`backend/app/config.py` 或新建 `backend/app/consumption_forecast.py`
   - 内容：`CONSUMPTION_FORECAST_UNIT_PRICES = {"L": 14.5, "N": 30.0, "X": 30.0}`
   - 验证：`python -c "from app.config import CONSUMPTION_FORECAST_UNIT_PRICES; print(CONSUMPTION_FORECAST_UNIT_PRICES)"`

2. **A2: 预测消费引擎方法**
   - 文件：`backend/app/services/analytics.py`
   - 新增方法：`forecast_consumption()` 替代 `predict_monthly_payment()`
   - 子方法：`_get_usage_baseline()`（用量基线）、`_cold_start_usage()`（冷启动）、`_trim_outliers()`（离群）、`_calculate_confidence()`（置信度）
   - 保留旧方法 `predict_monthly_payment()` 暂不删除（兼容）
   - 验证：编写测试用例覆盖保持/冷启动/离群/活跃度场景

3. **A3: 预测摘要方法**
   - 文件：`backend/app/services/analytics.py`
   - 新增方法：`get_forecast_summary()` 替代 `get_prediction_summary()`
   - 返回：`total_forecast`, `actual_this_month`, `month_over_month_change`, `active_customer_count`, `total_customer_count`, `confidence`

4. **A4: 预测趋势方法**
   - 文件：`backend/app/services/analytics.py`
   - 新增方法：`get_forecast_trend()` 替代 `get_prediction_trend()`
   - 返回 12 个月数据，含 `is_actual` 标记

5. **A5: data-readiness 方法**
   - 文件：`backend/app/services/analytics.py`
   - 新增方法：`get_data_readiness()`
   - 查询 `daily_consumptions` 时间覆盖、客户覆盖

6. **A6: 新接口路由**
   - 文件：`backend/app/routes/analytics.py`
   - 新增 3 个路由：`consumption/forecast`, `consumption/forecast-trend`, `consumption/data-readiness`
   - 保留旧路由（prediction/monthly, prediction/trend）

7. **A7: 预测准确度追踪**
   - 文件：`backend/app/services/analytics.py`
   - 新增方法：`record_prediction_accuracy()` 或集成到现有日志
   - 记录每月总预测 vs 实际消耗，计算 MAPE
   - 偏差>30% 发送通知（webhook 或内部信号）

8. **A8: 缓存更新**
   - 文件：`backend/app/routes/analytics.py` + `backend/app/services/analytics.py`
   - 新接口使用缓存（TTL 30 分钟）
   - 同步任务完成时清除 `analytics_prediction` 缓存

### Phase B: 前端改造（2 天）

9. **B1: API 层更新**
   - 文件：`frontend/src/api/analytics.ts`
   - 新增 `getConsumptionForecast()`, `getConsumptionForecastTrend()`, `getDataReadiness()`
   - 保留旧函数（兼容）

10. **B2: 页面实现**
    - 文件：`frontend/src/views/analytics/Forecast.vue`
    - 改造核心：接口调用、字段映射、新增组件
    - 保持模板结构不变，修改数据绑定和渲染逻辑

11. **B3: 新增子组件**
    - 文件：可选拆分 `DataReadinessBanner.vue`（数据就绪度横幅）
    - 或直接内联在 Forecast.vue 中

12. **B4: 侧边栏 + 路由更新**
    - 文件：`frontend/src/components/layout/AppSidebar.vue`
    - 文件：`frontend/src/composables/useAppLayout.ts`
    - "预测回款"→"预测消费"

### Phase C: 验证（0.5 天）

13. **C1: 后端测试**
    - 运行现有测试套件：`cd backend && make test`
    - 新增测试覆盖预测算法逻辑

14. **C2: 前端验证**
    - 运行 `npm run type-check`（类型检查）
    - 运行 `npm run dev` 启动，手动验证页面

15. **C3: 端到端验证**
    - 验证页面加载无报错
    - 验证统计卡片、趋势图、明细表数据正确
    - 验证横幅和置信度标签显示正确
    - 验证新客户冷启动逻辑
    - 验证休眠客户剔除逻辑

## 验证命令

```bash
# 后端
cd backend && python -m pytest tests/ -x -q --cov=app --cov-fail-under=50

# 前端类型检查
cd frontend && npm run type-check

# 前端开发服务器
cd frontend && npm run dev
```

## 风险文件 / 回滚点

| 风险文件 | 风险 | 回滚操作 |
|----------|------|---------|
| `backend/app/services/analytics.py` | 预测算法错误影响准确性 | git checkout 旧版本 |
| `backend/app/routes/analytics.py` | 路由冲突或旧接口被覆盖 | 保留旧路由不变 |
| `frontend/src/views/analytics/Forecast.vue` | 页面渲染错误 | 保留旧组件，新改造在分支上 |
| `frontend/src/api/analytics.ts` | API 调用失败 | 保留旧函数，新函数独立添加 |

## 前置检查（task.py start 前）

- [ ] 新分支 `feature/optimize-forecast-page` 已创建
- [ ] 工作区干净
- [ ] 后端开发环境可用（PostgreSQL 运行中）
- [ ] 前端开发环境可用（npm install 已完成）
- [ ] 必须同步任务状态已修复（假完成 bug）← 高优先级前提
