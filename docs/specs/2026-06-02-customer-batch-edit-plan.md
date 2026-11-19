# 客户批量编辑 — 实施计划（v1）

> 归档来源：`.omo/plans/customer-batch-edit-plan.md`（2026-11-19 蒸馏归档，原件已删除）
> 状态：已实施 —— 落点 `backend/app/routes/customers.py`（`@customers_bp.post("/batch-update")`）、`backend/app/services/customers.py`（`batch_update_customers`）、前端 `frontend/src/views/customers/components/BatchToolbar.vue` 与 `CustomerBatchEditModal.vue`
> 关联：`docs/specs/2026-06-01-customer-batch-edit-prd.md`（需求来源）
> 锚点说明：文中 `文件:行号` 为 2026-06 期快照，定位以符号名与路径为准

## Context

**原始请求**：在客户管理页面搜索结果中增加多选功能，多选后允许选择多个共同的字段进行批量修改。

**PRD 约束**（详见 PRD 文档）：

- 11 个可批量编辑字段：运营经理、商务经理、合作状态、重点客户、房产客户、结算方式、结算周期、是否启用结算、停用、账号类型、计费策略
- 排除字段：`company_id`、`name`、`email`、`notes`（唯一标识和自由文本不适合批量修改）
- 失败策略：部分成功不回滚，记录失败明细
- v1 不做：跨页全选（v1.2）、前端埋点（v1.2）、旧值对比预览（v1.1）、逐客户权限校验

## Approach

### 1. 后端 API 契约

`POST /api/v1/customers/batch-update`（`@auth_required` + `customers:edit` 端点级权限，v1 不逐客户校验）：

- 入参：`customer_ids: list[int]`（非空）、`fields: dict`（非空，键须在 `updatable_fields` 白名单内）
- 出参：
  ```json
  {
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "failed_list": [{"customer_id": 2, "reason": "无编辑权限"}]
  }
  ```
- `customer_ids` 超过 100 个 → 400，文案"单次批量编辑上限为 100 个客户，请分批操作"

### 2. 服务方法 `batch_update_customers(customer_ids, fields, db_session, current_user)`

要点：

- 校验：`customer_ids` 非空、`fields` 非空、字段键在 `update_customer` 的 `updatable_fields` 白名单内；非白名单字段记入 `failed_list`（原因"字段不可编辑"）
- **独立事务策略**：逐客户处理，任一客户失败不影响其他客户（后到者覆盖前者），部分失败不回滚
- 审计：复用 `build_batch_audit_summary` + `create_audit_entry`，`operation="batch_update"`
- 缓存：`cache_service.invalidate_customer_cache()`（不带参数清除所有列表缓存）
- 不改现有 `update_customer` 方法；参考实现模式 `routes/tags.py` 的 `batch_add_customer_tags`

### 3. 前端实现

- 表格 `row-selection`（`row-key="id"`）+ `selectedCustomerIds` 数组（分页切换保留选中）；选中 ≥1 条显示"批量编辑"按钮与"已选择 X 条"
- 批量编辑对话框：标题"批量编辑（已选择 X 个客户）"；11 个字段复选框 + 输入控件（下拉/开关），未勾选字段控件禁用
- `is_real_estate` 为三态（true/false/null），用 `a-select` 而非 `a-switch`
- F-1.4 简化版预览：点"提交"先弹预览确认（影响客户数 + 字段变更摘要，不含旧值），确认后才发请求
- API 封装 `batchUpdateCustomers(customerIds, fields)` → `POST /api/v1/customers/batch-update`；成功后清已选 + 刷新列表，部分失败展示失败明细
- 超时 10s、网络断联均提示且对话框保持打开可重试

## Critical files & anchors

- `backend/app/services/customers.py` — `batch_update_customers` 服务方法（白名单校验 / 独立事务 / 审计 / 缓存清理）
- `backend/app/routes/customers.py` — `POST /batch-update` 端点注册
- `backend/app/utils/audit_helpers.py` — `build_batch_audit_summary` / `create_audit_entry`（复用）
- `backend/app/cache/base.py` — `invalidate_customer_cache`（`customer_id=None` → `invalidate_pattern("cache:customer_list:*")`）
- `frontend/src/api/customers.ts` — `batchUpdateCustomers`
- `frontend/src/views/customers/Index.vue` — 当时实现位置（多选 + 对话框）；后重构拆出 `components/BatchToolbar.vue`、`components/CustomerBatchEditModal.vue`
- 测试：`backend/tests/unit/test_batch_update.py`（8 场景）、`frontend/tests/customer-batch-edit.spec.ts`（5 场景）

## Verification

### 验收命令

```bash
# 后端
pytest backend/tests/unit/test_batch_update.py -v          # 8 场景全过
curl -X POST http://localhost:8000/api/v1/customers/batch-update \
  -H "Authorization: Bearer {token}" -H "Content-Type: application/json" \
  -d '{"customer_ids":[1],"fields":{"is_key_customer":true}}'   # 成功响应

# 前端
npm run lint -C frontend      # 无错误
npm run build -C frontend     # 构建成功
npx vue-tsc --noEmit          # 类型通过

# E2E
npx playwright test customer-batch-edit.spec.ts   # 5 场景全过
```

### 验收结论（2026-06-02）

- Plan Compliance Audit：Must Have 6/6、Must NOT Have 5/5、Tasks 7/7 → APPROVE
- Code Quality Review：Build / Lint / TypeScript 均 PASS → APPROVE
- Manual QA：Scenarios 6/6 pass、Integration PASS、Edge Cases 6 tested（空态 / 非法输入 / 快速操作）→ APPROVE
- Scope Fidelity：Tasks 4/4 compliant、无范围外污染 → APPROVE

### 关键边界（回归时的易错点）

- 上限 100 在服务层拒绝（400），文案固定
- 部分失败不回滚：成功客户已落库，仅失败者进 `failed_list`
- 缓存清理用不带参调用（清全部列表缓存），避免只清单客户键
- 端点级权限即 `customers:edit`；无权限 403

## Assumptions

- 并发冲突以"后到者覆盖"处理，v1 不引入乐观锁版本号。
- 审计与缓存复用既有实现，未新建平行机制。
- E2E 覆盖网络断联恢复场景（断网提交 → 提示 → 对话框不关可重试）。

## 实施结果（截至 2026-11-19 核实）

- 后端 `POST /api/v1/customers/batch-update` 与 `batch_update_customers` 均在位（`routes/customers.py`、`services/customers.py`），100 上限、`operation="batch_update"` 审计、缓存清理生效。
- 前端已重构为 `components/BatchToolbar.vue`（多选工具条）与 `components/CustomerBatchEditModal.vue`（字段选择对话框，含 `BatchFailedItem` 类型），契约未变。
