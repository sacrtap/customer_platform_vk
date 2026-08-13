# 技术设计：预测消费页面 apply_to 参数逻辑修复

## 架构决策

### 1. 后端月份范围计算逻辑

**决策**：在 `get_forecast_trend` 方法中实现月份范围过滤

**理由**：
- 保持 API 接口签名不变，避免前端大规模改动
- 后端统一控制数据范围，保证数据一致性
- 符合现有代码架构，不引入新的服务层

**实现方案**：
```python
# 计算起始月份
if apply_to == 'future_only':
    start_month = current_month  # 当前月
else:
    start_month = 1  # 全年

# 计算结束月份
if forecast_months:
    end_month = min(start_month + forecast_months - 1, 12)
else:
    end_month = 12

# 生成月份列表
months = list(range(start_month, end_month + 1))
```

### 2. 前端趋势图动态渲染

**决策**：前端根据后端返回的月份数据动态生成 X 轴标签

**理由**：
- 后端返回的数据已经包含月份信息
- 前端只需根据实际数据渲染，不需要额外的范围计算
- 保持前后端数据一致性

**实现方案**：
```typescript
// 从后端数据提取月份标签
const monthLabels = data.map(item => {
  const month = parseInt(item.month.split('-')[1])
  return `${month}月`
})

// 使用动态标签渲染图表
chart.setOption({
  xAxis: {
    data: monthLabels
  }
})
```

### 3. 数据格式保持兼容

**决策**：保持现有的数据返回格式不变

**理由**：
- 避免前端大规模改动
- 保持 API 向后兼容
- 减少测试范围

**数据格式**：
```json
{
  "month": "2026-08",
  "forecast": 12345.67,
  "actual": null,
  "is_actual": false
}
```

## 数据流

```
前端请求 (apply_to, forecast_months)
    ↓
后端 get_forecast_trend
    ↓
计算月份范围 (start_month, end_month)
    ↓
查询历史数据 + 生成预测数据
    ↓
返回月份列表数据
    ↓
前端根据数据动态渲染图表
```

## 边界条件处理

### 1. 当前月是 12 月

**场景**：current_month = 12, forecast_months = 6

**处理**：
- start_month = 12
- end_month = min(12 + 6 - 1, 12) = 12
- 返回 1 个月的数据（仅 12 月）

**理由**：MVP 限制不跨年，避免复杂的年份切换逻辑

### 2. forecast_months 超过 12

**场景**：forecast_months = 18

**处理**：
- end_month = min(start_month + 18 - 1, 12) = 12
- 最多返回 12 个月的数据

**理由**：MVP 限制，后续迭代可扩展

### 3. forecast_months 为 0 或负数

**场景**：forecast_months = 0

**处理**：
- 返回空数组
- 前端显示空图表

**理由**：合理的边界处理，避免异常

## 测试策略

### 1. 后端单元测试

**测试用例**：
- apply_to='all', forecast_months=12 → 返回 12 个月
- apply_to='future_only', current_month=8, forecast_months=6 → 返回 8-12 月
- apply_to='future_only', current_month=12, forecast_months=6 → 返回 12 月
- forecast_months=0 → 返回空数组
- forecast_months=18 → 返回 12 个月

### 2. 前端测试

**测试用例**：
- 渲染 12 个月的数据
- 渲染 5 个月的数据（8-12 月）
- 渲染 1 个月的数据（12 月）
- 渲染空数据

### 3. 端到端测试

**测试场景**：
- 选择"更新历史及后续月份" → 显示全年 12 个月
- 选择"仅后续月份"，forecast_months=6 → 显示 8-12 月
- 修改 forecast_months → 图表动态更新

## 风险评估

### 1. 低风险

- API 接口签名不变
- 数据格式保持兼容
- 前端改动范围可控

### 2. 中风险

- 前端图表组件可能需要调整以适应动态月份范围
- 需要确保所有边界条件都正确处理

### 3. 缓解措施

- 充分的单元测试覆盖
- 端到端验证
- 代码审查

## 后续迭代

### 1. 跨年预测支持

**需求**：支持 forecast_months > 12 的场景

**技术方案**：
- 后端需要处理年份切换
- 数据格式需要包含年份信息
- 前端需要支持跨年渲染

### 2. 更灵活的月份选择

**需求**：支持用户自定义起始月份

**技术方案**：
- 新增 start_month 参数
- 前端提供月份选择器

## 总结

本次修复主要涉及后端月份范围计算和前端动态渲染两个核心改动。通过保持 API 接口和数据格式不变，最小化改动范围，降低风险。MVP 版本限制不跨年，后续迭代可扩展支持。
