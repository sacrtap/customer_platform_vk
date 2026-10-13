# 开放平台余额白名单 — 技术设计

## 架构与边界

```
前端 BalanceWhitelist.vue（系统管理）
  └─ /api/v1/balance-whitelists/*（新蓝图 balance_whitelist_bp，JWT + balance_whitelist:manage）
       └─ BalanceWhitelistService（CRUD + 按 ERP 批量导入）
            └─ balance_whitelists 表（新，customer_id 唯一）

开放平台 GET /api/v1/balances（openapi_customer_bp，API-Key）
  └─ _build_customer_balance_stmt() 查询 → _format_balance_rows()
       └─ 新增：查询白名单 map（customer_id → static_balance），格式化时覆盖 balance
```

边界：`balance_whitelists` 仅服务于开放平台全量余额接口；不触碰 `CustomerBalance` 结算链路，不改变 `/api/v1/erp/balances`。

## 数据模型（新表 balance_whitelists）

| 列 | 类型 | 说明 |
|---|---|---|
| id | Integer PK autoincrement | |
| customer_id | Integer FK customers.id, unique, NOT NULL | 白名单客户 |
| static_balance | DECIMAL(12,2) NOT NULL | 静态余额，默认 1000.00 |
| created_at / updated_at / deleted_at | 沿用 BaseModel | 软删除用于「移出白名单」 |

- `deleted_at IS NOT NULL` 视为已移出；接口查询仅取未删除记录。
- 唯一约束 `customer_id`：同一客户只有一条白名单记录（重复导入 → 幂等跳过）。
- 移出采用软删除（沿用 SoftDeleteMixin）；再次添加/导入时存在软删记录则**恢复原记录并保留既有 static_balance**（不覆盖人工调整值，与 AC6 幂等语义一致；单独添加显式传新余额时覆盖为传入值）。

## 后端 API 设计

蓝图 `balance_whitelist_bp = Blueprint("balance_whitelists", url_prefix="/api/v1/balance-whitelists")`，注册于 `backend/app/main.py`（与 erp_system_bp 相邻）。全部端点 `@auth_required` + `@require_permission("balance_whitelist:manage")`（列表 GET 同权限，参照 erp_systems 现状）。

| 端点 | 方法 | 请求 | 响应 data |
|---|---|---|---|
| `/` | GET | page/page_size/keyword(可选，按客户名/company_id 过滤) | `{items:[{id, customer_id, company_id, customer_name, erp_system, static_balance, created_at}], total}` |
| `/batch-import` | POST | `{erp_system_value: str}` + Query `dry_run` | `{dry_run, imported, skipped}`（预检不落库；真实导入单事务幂等） |
| `/` | POST | `{customer_id: int, static_balance?: number(默认1000)}` | `{id, ...}`（已存在 → 400「已在余额白名单中」；软删记录 → 恢复并覆盖余额） |
| `/<id>` | PUT | `{static_balance: number}` | `{id, ...}` |
| `/<id>` | DELETE | — | `{success: true}`（软删除） |

- **批量导入事务**：`async with db_session.begin():` 内查询该 ERP 全部有效客户（`Customer.erp_system == value AND deleted_at IS NULL AND is_disabled != true`），逐条检查白名单已存在（含软删恢复）后 insert。单事务保证原子性。
- **static_balance 校验**：非负、两位小数精度（后端 Decimal 解析，前端输入限制）。

## 开放平台接口改造（openapi.py）

`get_all_customer_balances` 执行原查询后：

```python
whitelist_result = await db_session.execute(
    select(BalanceWhitelist.customer_id, BalanceWhitelist.static_balance)
    .where(BalanceWhitelist.deleted_at.is_(None))
)
whitelist_map = {cid: float(sb) for cid, sb in whitelist_result.all()}
```

在 `_format_balance_rows`（新增可选参数 `whitelist_map`）中：若 `row.customer_id`（DB 主键）命中白名单，`balance = whitelist_map[customer_id]`，不再使用 `total - used`。其余行不变。

- `_format_balance_rows` 目前从 row 取 `company_id`（即 DB `Customer.id`）作为响应 `customer_id`；需注意白名单 map 的键是 DB 主键 `Customer.id`，而查询 SELECT 的是 `Customer.company_id` —— **必须在语句中补充取回 `Customer.id`**（追加一列，格式函数对应解包），否则无法按主键匹配白名单。
- 契约不变：字段结构、排序（company_id 升序）、过滤语义完全保留。

## 权限与迁移

alembic 迁移 `down_revision = "a2b3c4d5e6f7"`（当前 head）：
1. `op.create_table("balance_whitelists", ...)`（含唯一索引 ix_balance_whitelists_customer_id）。
2. `bulk_insert` 权限 `balance_whitelist:manage`（name=管理余额白名单, module=system）。
3. `INSERT INTO role_permissions ... WHERE r.name='超级管理员' AND p.code='balance_whitelist:manage' ON CONFLICT DO NOTHING`。
4. downgrade 反向清理。

模型 `backend/app/models/balance_whitelist.py` + 注册进 `models/__init__.py`。

## 前端设计

- `types/index.ts`：`BalanceWhitelistItem { id, customer_id, company_id, customer_name, erp_system, static_balance, created_at }`。
- `api/balanceWhitelist.ts`：`getBalanceWhitelist(params)` / `batchImportBalanceWhitelist(erp_system_value)` / `addBalanceWhitelist(data)` / `updateBalanceWhitelist(id, data)` / `removeBalanceWhitelist(id)`。
- `views/system/BalanceWhitelist.vue`：参照 `ErpSystems.vue` 页面骨架（PageHeader + table-section + a-modal）。
  - 顶部操作：「按 ERP 批量导入」（弹窗选择 ERP 下拉 → 预检展示将新增/已存在跳过数 → 确认导入）+「添加客户」（弹窗关键字搜索客户下拉 → 确认添加，余额默认 1000 可改）。
  - 行操作：编辑静态余额（a-modal 表单）/ 移出白名单（a-popconfirm）。
- 路由：`router/index.ts` system children 新增 `{ path: 'balance-whitelist', component: BalanceWhitelist.vue, meta: { requiresPermission: 'balance_whitelist:manage' } }`。
- 侧边栏：`AppSidebar.vue` 系统管理组新增按钮（`v-if="can('balance_whitelist:manage')"`，`/system/balance-whitelist`）。
- 客户选择数据源：复用现有客户列表 API（`/api/v1/customers?keyword=`）搜索。

## 兼容性与回滚

- 白名单表初始为空 → 上线前后 `/api/v1/balances` 行为一致（无行为回归）。
- 接口响应结构不变，开放平台调用方无感知。
- 回滚：`alembic downgrade` 迁移即可（删表 + 删权限）；接口改造与前端路由随代码回退。
- ERP 系统被删除（软删）时，其下白名单客户仍保留（白名单不随 ERP 级联删除），界面操作不受影响。

## 风险与权衡

- **匹配键**：白名单以 DB 主键 `customer_id` 关联，接口需同时取回 `Customer.id`（见改造说明）；避免用 company_id 匹配（其也可能变化）。
- **批量导入量级**：大 ERP 名单下单事务插入多行，采用 executemany/批量 add 一次提交，避免逐行 commit。
- **静态余额覆盖语义**：白名单客户接口余额不再反映真实充消余额，属产品需求；文档中注明以静态值为准。
- 权限粒度沿用项目惯例（模块级 manage），不与 api_keys 等细粒度混淆。
