# 审计日志优化实施计划

**生成日期**: 2026-05-20
**最后更新**: 2026-05-20 (经 graphify 影响范围分析后修订)
**状态**: 待执行确认

---

## 一、修改范围

### 步骤 1：前端 — 移除 formatAction 中文映射

**文件**: `frontend/src/views/system/AuditLogs.vue`

- 删除 `formatAction()` 函数及 `actionMap` 映射表（第 267-282 行）
- 操作类型列直接显示 `record.action`（原始英文）
- 移除 `#action` 模板中的 `{{ formatAction(record.action) }}` → 改为 `{{ record.action }}`
- 清理未使用的 `formatAction` 函数

**预期效果**: 所有操作类型统一显示英文（如 `create`、`batch_create`、`add_tag`、`recharge`）

---

### 步骤 2：中间件 — skip_paths 精确化（经 graphify 分析修订）

**文件**: `backend/app/middleware/audit.py`（第 67-83 行）

⚠️ **修订原因**：
1. 原计划使用宽泛的 `/api/v1/billing/` 会覆盖所有 billing 端点，包括 pricing-rules CRUD 和 delete invoice 等当前**没有手动审计**的端点，会导致审计丢失
2. 中间件对 `/api/v1/files/` 使用 `startswith()` 前缀匹配，但对其他路径使用 `in skip_paths` 精确匹配
3. `/api/v1/billing/invoices/` 如果放在 `skip_paths` 中，会被 `in` 精确匹配忽略（因为实际路径是 `/billing/invoices/123/submit`）

**修正方案**：精确路径 + 前缀匹配 + 动作端点后缀判断：

```python
skip_paths = [
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/auth/me",
    "/api/v1/webhooks/invoice-confirmation",
    "/api/v1/webhooks/payment-notify",
    "/api/v1/files/",  # files 模块手动审计
    "/api/v1/billing/recharge",  # billing 模块手动审计（记录业务语义和计算结果）
]

if request.path in skip_paths:
    return

# Billing 发票动作端点：只跳过状态变更端点，生成/折扣/删除保持中间件自动审计
if request.path.startswith("/api/v1/billing/invoices/"):
    action_endpoints = ("/submit", "/confirm", "/pay", "/complete", "/cancel")
    if any(request.path.endswith(action) for action in action_endpoints):
        return
```

**影响范围对比**（基于 graphify 社区 7/8/81 分析）：

| 端点                              | 之前行为                     | 修正后行为                                |
| --------------------------------- | ---------------------------- | ----------------------------------------- |
| `POST /billing/recharge`            | ❌ 重复记录 + 语义错误        | ✅ skip → 手动记录 `recharge`              |
| `POST /invoices/*/submit`           | ❌ action="create" 错误       | ✅ skip → 手动记录 `submit`                |
| `POST /invoices/*/confirm`          | ❌ action="create" 错误       | ✅ skip → 手动记录 `confirm`               |
| `POST /invoices/*/pay`              | ❌ action="create" 错误       | ✅ skip → 手动记录 `pay`                   |
| `POST /invoices/*/complete`         | ❌ action="create" 错误       | ✅ skip → 手动记录 `complete`              |
| `POST /invoices/*/cancel`           | ❌ action="create" 错误       | ✅ skip → 手动记录 `cancel`                |
| `PUT /pricing-rules/:id`            | ✅ action="update" (正确)      | ✅ 保持中间件自动审计                        |
| `DELETE /pricing-rules/:id`         | ✅ action="delete" (正确)      | ✅ 保持中间件自动审计                        |
| `DELETE /invoices/:id`              | ✅ action="delete" (正确)      | ✅ 保持中间件自动审计                        |
| `POST /billing/invoices/generate`   | ✅ action="create" (正确)      | ✅ 保持中间件自动审计                        |
| `PUT /invoices/:id/discount`        | ✅ action="update" (正确)      | ✅ 保持中间件自动审计                        |

---

### 步骤 3：充值 changes 标准化

**文件**: `backend/app/routes/billing.py`（第 403-421 行）

变更前：
```python
changes={"customer_id": customer_id, "real_amount": float(real_amount), "bonus_amount": float(bonus_amount)}
```

变更：在 recharge 调用前获取 before 余额，充值后获取 after 余额
```python
balance_before = await balance_service.get_balance_by_customer_id(customer_id)
record = await balance_service.recharge(...)
balance_after = await balance_service.get_balance_by_customer_id(customer_id)

changes={
    "before": {"real_amount": float(balance_before.real_amount), "bonus_amount": float(balance_before.bonus_amount)},
    "after": {
        "real_amount": float(balance_after.real_amount),
        "bonus_amount": float(balance_after.bonus_amount),
        "recharge_real": float(real_amount),
        "recharge_bonus": float(bonus_amount),
    },
    "customer_id": customer_id,
}
```

**注意**: `CustomerBalance` 模型余额字段为 `real_amount`（实充余额）和 `bonus_amount`（赠送余额），非 `real_balance`。`BalanceService.get_balance_by_customer_id()` 已在图谱 community 7 中确认存在。

---

### 步骤 4：发票操作补充手动审计

**文件**: `backend/app/routes/billing.py`（5 个端点）

| 端点 | action | changes |
|------|--------|---------|
| `submit_invoice` (#1112) | `submit` | `{"before": {"status": "draft"}, "after": {"status": "paid_pending_confirm"}}` |
| `confirm_invoice` (#1135) | `confirm` | `{"before": {"status": "paid_pending_confirm"}, "after": {"status": "confirmed"}}` |
| `pay_invoice` (#1154) | `pay` | `{"before": {"payment_proof": null}, "after": {"payment_proof": "..."}}` |
| `complete_invoice` (#1177) | `complete` | `{"before": {"status": "confirmed", "real_amount": "...", "bonus_amount": "..."}, "after": {"status": "completed", "real_amount": "...", "bonus_amount": "..."}}`（含余额扣减变化） |
| `cancel_invoice` (#1196) | `cancel` | `{"before": {"status": "draft"}, "after": {"status": "cancelled"}}` |

**实现模式**（以 submit 为例）：
1. 操作前查询发票获取 before 状态
2. 执行操作
3. 操作后查询获取 after 状态
4. 记录审计日志
5. 清除缓存

---

### 步骤 5：密码重置/角色分配添加 changes

**文件**: `backend/app/routes/users.py`

| 操作 | 行号 | changes 内容 |
|------|------|-------------|
| 密码重置 | #262 | `{"before": {"password_hash": "***MASKED***"}, "after": {"password_hash": "***RESET***"}}` |
| 角色分配 | #307 | 已有 `{"role_id": role_ids}`，格式可接受，无需修改 |

---

### 步骤 6：批量标签操作补充 changes

**文件**: `backend/app/routes/tags.py`

| 操作 | 行号 | changes 内容 |
|------|------|-------------|
| 批量添加标签 | #395 | `{"after": {"success_count": N, "error_count": M}, "customer_ids": [...]}` |
| 批量移除标签 | #464 | `{"after": {"removed_count": N}, "customer_ids": [...]}` |

注：customer_ids 建议最多记录 10 个，避免 changes 字段过长。

---

### 步骤 7：前端 API 响应字段补充（已完成）

**文件**: `backend/app/routes/audit_logs.py`

已在上轮修复中添加：
- `operation_type`: 操作类型分类 (standard/batch/relation/sensitive)
- `extra_metadata`: 扩展元数据

**前端 TypeScript 接口** (`AuditLogs.vue`) 已同步更新。

---

### 步骤 8：文件删除操作补充 record_id

**文件**: `backend/app/routes/files.py`（#522-538）

补充 `record_type="file"`（record_id 已从路径提取）。

---

## 二、Graphify 影响分析摘要

**图谱数据**: 7,340 节点 · 8,688 边 · 619 社区 · 92% EXTRACTED / 8% INFERRED

### 核心审计相关社区
| 社区 | 内容                  | 关联节点数 |
|------| --------------------- | ---------- |
| 7    | Billing Models/Services | 高      |
| 8    | Billing Routes          | 高      |
| 81   | Audit Helpers           | 中      |
| 349  | Middleware              | 中      |

### 调用链分析
```
audit_middleware() (community 349)
  ← called by create_app() (main.py)

create_audit_entry() (community 81)
  ← called by: users.py, customers.py, tags.py, billing.py, database_management.py
```

### 额外风险发现
1. **skip_paths 宽泛路径风险**: `/api/v1/billing/` 会跳过 pricing-rules CRUD → 已修正为精确路径
2. **测试覆盖**: `test_audit_helpers_db.py` (3 tests) + `test_audit_logs_api.py` (4 tests) — 修改后需验证
3. **无数据库迁移需求**: AuditLog 模型的 `operation_type` 和 `extra_metadata` 已存在于 alembic 中

---

## 三、验证计划

1. **后端测试**: `pytest tests/integration/test_audit_logs_api.py tests/integration/test_audit_helpers_db.py -v`
2. **代码质量**: `ruff check app/routes/ app/middleware/ && ruff format --check`
3. **前端验证**: 手动验证操作类型显示英文、变更详情显示 before/after、批量操作显示摘要

---

## 四、根因分析摘要

1. 操作对象为空：部分路由未设置 record_id/record_type（database_management.py、files.py）
2. 变更详情为空：部分路由未设置 changes（billing.py 充值格式非 before/after、users.py 密码重置无 changes）
3. 操作类型不统一：前端 formatAction 只映射了部分 action，批量操作等未覆盖
4. 重复审计日志：billing 充值同时被中间件和手动记录 → skip_paths 精确化解决

---

## 五、架构决策

- billing 模块采用 **精确 skip_paths + 手动审计**（方案 B 修正版），与 files 模块架构一致
- 充值操作需要获取 before/after 余额记录余额变化
- 密码重置不记录密码内容，只记录操作事实（安全考量）
- pricing-rules CRUD 和 invoice DELETE 保持中间件自动审计（避免不必要的手动审计复杂度）
