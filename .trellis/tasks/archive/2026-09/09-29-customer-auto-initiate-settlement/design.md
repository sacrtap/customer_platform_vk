# Design：客户「自动发起结算」

## 字段与 NULL 语义

- `customers.auto_initiate_settlement`：`Boolean, nullable=True, default=True`，默认「是」。
- NULL = 是（历史行），筛选「是」用 `or_(is_(True), is_(None))`，筛选「否」严格 `is_(False)`（与 `is_settlement_enabled` 同侧兼容模式，见 `.trellis/spec/backend/database-guidelines.md`）。
- create 时显式 `data.get("auto_initiate_settlement", True)` 写入，保证新客户非 NULL；update 通过 `updatable_fields` 支持写入。

## 改动面

### 后端

| 文件 | 改动 |
|---|---|
| `backend/app/models/customers.py` | Customer 加字段（default=True） |
| `backend/alembic/versions/a2b3c4d5e6f7_*.py` | 新增列（nullable，无 server_default，历史行为 NULL） |
| `backend/app/services/customers.py` | create 默认 True；update updatable_fields + 筛选条件 + batch 白名单 |
| `backend/app/routes/customers.py` | list/export 解析 `auto_initiate_settlement` 布尔参数；列表项/详情/导出列序列化 |
| `backend/tests/unit/test_customer_service.py` | 创建默认值断言、update 字段用例、筛选 true/false NULL 兼容用例 |
| `backend/tests/integration/test_customers_api.py` | 创建默认/显式、更新、列表筛选 true/false（含 NULL）用例 |
| `backend/tests/integration/conftest.py` `backend/tests/e2e/conftest.py` | `create_all` 不 ALTER 已有表，补 `ALTER TABLE customers ADD COLUMN auto_initiate_settlement BOOLEAN` |

### 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/types/index.ts` | Customer 加 `auto_initiate_settlement: boolean \| null` |
| `frontend/src/api/customers.ts` | `CustomerCreate`/getCustomers/createCustomer/updateCustomer 类型 |
| `frontend/src/composables/updateCustomerType.ts` | UpdateCustomerData |
| `frontend/src/composables/useCustomerList.ts` | 默认筛选 null（全部）+ buildParams 传递 |
| `frontend/src/views/customers/components/CustomerFilters.vue` | Filters 接口 + 桥接 computed + more-row FilterDropdown |
| `frontend/src/views/customers/components/AddCustomerModal.vue` | 表单 select（默认 true）+ payload |
| `frontend/src/views/customers/detail/EditCustomerDialog.vue` | a-switch（回填 `?? true`）+ 提交 |
| `frontend/src/composables/useCustomerDetail.ts` | EditForm 类型/默认/回填 |
| `frontend/src/views/customers/detail/CustomerBasicTab.vue` | 展示（NULL 视为是） |
| `frontend/src/views/customers/components/CustomerBatchEditModal.vue` | checkbox + switch 批量编辑 |

## 关键决策

1. **默认值落库非 NULL**：create 显式传默认，而非依赖 ORM default——保证 `筛「否」` 不含非预期项、导出列非 NULL。
2. **历史 NULL 兼容**：迁移不加 server_default（与 `is_settlement_enabled` 历史一致），筛选侧兼容。
3. **导入不动**：需求不含导入；导入客户未填该列时由 create 默认 true 兜底（导入不校验该列）。
4. **列表项补字段**：列表序列化原来不含 `is_settlement_enabled`，本次为保持前端 `Customer` 类型一致性一并补上新字段（不补既有 `is_disabled`，保持最小差异）。
