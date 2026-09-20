# Implement — 筛选项增强

## 步骤

1. **后端 `services/customers.py`** `get_all_customers`：
   - 在现有 `is_key_customer` / `is_real_estate` 条件旁追加 `is_settlement_enabled` 条件。
   - 追加 `is_disabled` 条件；`False` 时用 `or_(Customer.is_disabled.is_(False), Customer.is_disabled.is_(None))` 兼容 NULL。
2. **后端 `routes/customers.py`** `list_customers`：解析 `is_settlement_enabled`、`is_disabled` 布尔参数，写入 filters（参照 `is_key_customer`）。
3. **前端 `api/customers.ts`** `getCustomers` 参数类型增加 `is_settlement_enabled?: boolean | string`、`is_disabled?: boolean | string`。
4. **前端 `useCustomerList.ts`**：
   - `createDefaultFilters` 增加 `is_settlement_enabled: null`、`is_disabled: null`。
   - `buildParams` 增加两个参数传递（`is_key_customer` / `is_real_estate` 已有）。
5. **前端 `CustomerFilters.vue`**：
   - 定义 4 个布尔桥接 computed（string ↔ boolean|null）。
   - 在 `more-row` 追加 4 个 FilterDropdown：是否结算、是否重点客户、是否房产客户、是否停用。
6. **后端测试** `backend/tests/unit/test_customer_service.py`：为 `is_settlement_enabled`、`is_disabled`（含 NULL 兼容）增加筛选用例。

## 验证

- 后端：`cd backend && $BACKEND_DIR/.venv/bin/python -m pytest tests/unit/test_customer_service.py -q`（覆盖率 ≥25%）
- 前端：`cd frontend && npx vue-tsc --noEmit` 或项目类型检查命令（确认 README/Makefile）
- 运行前端 dev server + 后端，浏览器实际操作 4 个筛选项（是/否/全部 + 组合筛选）验证过滤结果
- 清理：临时调试代码删除

## 回滚点

- 每步改动可独立 revert；前后端不兼容风险低（后端缺参数时前端不传即可）。
