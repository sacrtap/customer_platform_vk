# 计费规则有效期重叠校验优化设计

**日期**: 2026-04-28
**状态**: 已审批
**方案**: 方案 A（最小修复）

---

## 背景

计费规则页面（`PricingRules.vue`）在新建规则时，需要约束：在有效期范围内，当客户名称、设备类型、楼层类型完全一致时，不允许创建有时间重叠的记录。

## 问题分析

| 问题 | 位置 | 说明 |
|------|------|------|
| 1. `layer_type` NULL 比较失败 | `services/billing.py:283` | `layer_type` 为 `None` 时，SQL `== None` 返回 UNKNOWN，导致校验漏掉 `layer_type` 为空的记录 |
| 2. 更新操作缺少重叠校验 | `services/billing.py:341-373` | `update_pricing_rule` 无任何有效期重叠校验，用户可编辑规则使其与其他规则产生时间重叠 |
| 3. 前端无预校验 | `PricingRules.vue:handleSubmit` | 完全依赖后端返回错误，用户体验差（填完整个表单后才被告知冲突） |
| 4. 无冲突检查 API | — | 前端无法提前获知是否存在冲突 |

## 设计

### 模块 1：修复 `create_pricing_rule` 的 `layer_type` NULL 比较

**文件**: `backend/app/services/billing.py`

**改动**: 将 `layer_type` 的 SQL 比较从直接 `==` 改为条件判断：

```python
if layer_type is None:
    layer_condition = PricingRule.layer_type.is_(None)
else:
    layer_condition = PricingRule.layer_type == layer_type
```

### 模块 2：`update_pricing_rule` 增加重叠校验

**文件**: `backend/app/services/billing.py`

**改动**: 在更新前检查有效期相关字段是否被修改，若是则执行重叠校验：
- 使用修改后的值（如果提供了）或原始值
- 排除自身记录（`exclude_id=rule_id`）
- 校验逻辑复用创建时的日期重叠判断

### 模块 3：提取统一校验方法 `_check_overlap`

**文件**: `backend/app/services/billing.py`

**新增方法**:
```python
async def _check_overlap(
    self,
    customer_id: int,
    device_type: str,
    layer_type: Optional[str],
    effective_date: date,
    expiry_date: Optional[date],
    exclude_id: Optional[int] = None,
) -> None:
    """检查是否存在有效期重叠的规则，存在则抛出 ValueError"""
```

**职责**:
1. 构建查询条件（正确处理 `layer_type` 为 `None` 的情况）
2. 如果 `exclude_id` 不为 `None`，排除该记录
3. 遍历已有规则检查日期重叠
4. 存在冲突则抛出 `ValueError`

### 模块 4：新增冲突检查 API

**路由**: `GET /api/v1/billing/pricing-rules/check-conflict`

**Query 参数**:
- `customer_id` (必填, int)
- `device_type` (必填, string)
- `layer_type` (必填, string)
- `effective_date` (必填, date)
- `expiry_date` (可选, date)
- `exclude_id` (可选, int) — 编辑时排除自身

**返回格式**:
```json
{
  "code": 0,
  "data": {
    "has_conflict": true,
    "conflicting_rules": [
      {
        "id": 5,
        "pricing_type": "fixed",
        "effective_date": "2026-01-01",
        "expiry_date": "2026-12-31"
      }
    ]
  }
}
```

**Service 层新增方法**:
```python
async def check_pricing_rule_conflict(
    self,
    customer_id: int,
    device_type: str,
    layer_type: Optional[str],
    effective_date: date,
    expiry_date: Optional[date],
    exclude_id: Optional[int] = None,
) -> List[PricingRule]:
    """查询与给定条件存在有效期重叠的规则，返回冲突列表"""
```

### 模块 5：前端提交前预校验

**文件**: `frontend/src/views/billing/PricingRules.vue`

**改动**: 在 `handleSubmit` 中，提交前先调用 `check-conflict` 接口：
- 有冲突：弹窗提示冲突规则详情（ID、计费类型、有效期）
- 无冲突：继续创建/更新操作

**文件**: `frontend/src/api/billing.ts`

**新增**:
```typescript
export const checkPricingRuleConflict = (params: ConflictCheckParams) =>
  http.get('/billing/pricing-rules/check-conflict', { params })
```

## 测试计划

| 测试场景 | 预期结果 |
|----------|----------|
| 创建规则：`layer_type` 为 `None`，存在相同条件的已有规则 | 抛出冲突错误 |
| 创建规则：`layer_type` 为 `"single"`，存在相同条件的已有规则 | 抛出冲突错误 |
| 创建规则：`layer_type` 不同 | 允许创建 |
| 更新规则：修改有效期导致与其他规则重叠 | 抛出冲突错误 |
| 更新规则：修改有效期但不重叠 | 允许更新 |
| 更新规则：不修改有效期相关字段 | 跳过校验 |
| API `check-conflict`：有冲突 | 返回冲突规则列表 |
| API `check-conflict`：无冲突 | 返回 `has_conflict: false` |
| 前端：提交前有冲突 | 弹窗提示冲突详情，阻止提交 |
| 前端：提交前无冲突 | 正常提交 |

## 影响范围

| 文件 | 改动类型 |
|------|----------|
| `backend/app/services/billing.py` | 修改 + 新增方法 |
| `backend/app/routes/billing.py` | 新增路由 |
| `frontend/src/api/billing.ts` | 新增 API 方法 |
| `frontend/src/views/billing/PricingRules.vue` | 修改 `handleSubmit` |
| `backend/tests/test_billing_service.py` | 新增测试用例 |
| `backend/tests/integration/test_billing_api.py` | 新增 API 测试 |
