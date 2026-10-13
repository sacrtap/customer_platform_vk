# 开放平台余额白名单功能

## Goal

系统管理模块新增「余额白名单」页面，允许按 ERP 名单批量导入客户、或单独添加客户，并为这些客户设定静态余额（默认 1000 元）。添加到白名单的客户，通过开放平台 `GET /api/v1/balances` 获取数据时优先返回该静态余额，其余客户仍返回计算余额。

## Background（已确认事实，来自代码证据）

- 开放平台接口 `backend/app/routes/openapi.py`：
  - `GET /api/v1/balances`（全量客户余额）与 `GET /api/v1/erp/balances?erp_channel=`（按 ERP 渠道）共用 `_build_customer_balance_stmt()`，均通过 API-Key 认证。
  - 当前余额 = `CustomerBalance.total_amount − used_total`（LEFT JOIN，无余额按 0），响应 `data: [{customer_id, customer_name, balance}]`，其中 `customer_id` 实为 `Customer.company_id`。
- ERP 名单：系统管理 →「ERP 系统」页面维护 `erp_systems` 字典表（`name` / `value` / `sort_order`）；客户通过 `Customer.erp_system = value` 关联。用户需求中「客户管理页面中设定的 ERP 名单」实际即此字典。
- 权限模式：alembic 迁移中 `bulk_insert` 权限 + 关联「超级管理员」角色；前端路由 `meta.requiresPermission` + `AppSidebar.vue` 菜单项 `can()` 控制。
- 新增表模式：alembic 迁移（head = `a2b3c4d5e6f7`）+ `backend/app/models/__init__.py` 注册。
- 批量导入参考：客户导入 `POST /api/v1/customers/import` 支持 `dry_run` 预检 → 行级错误（含行号）→ 前端二次确认后落库。

## Requirements

### 功能需求

- **R1 余额白名单页面**：系统管理模块新增「余额白名单」页面（路径 `/system/balance-whitelist`，权限 `balance_whitelist:manage`），展示白名单客户列表（客户 ID / 名称 / ERP / 静态余额 / 添加时间 / 操作），支持分页。
- **R2 按 ERP 批量导入**：选择某个 ERP 系统（按 `ErpSystem.value` 匹配），一次性导入该 ERP 下所有有效客户（未删除、未停用），默认静态余额 1000 元。导入前预检展示「将新增 N 条、已存在跳过 M 条」，二次确认后落库。
- **R3 单独添加**：从现有客户（按关键字搜索选择）单独添加单个客户，默认静态余额 1000 元。
- **R4 编辑与移除**：单个客户可编辑静态余额；可移出白名单（恢复接口真实余额显示）。
- **R5 接口优先级**：`GET /api/v1/balances` 对白名单客户返回静态余额（`balance = static_balance`），非白名单客户维持计算余额；接口契约（字段结构、`code`/`message`）不变。
- **R6 权限**：新增权限 `balance_whitelist:manage`（module=system），自动授予「超级管理员」角色；页面菜单按权限显示。

### 边界（Out of Scope）

- **不改 `GET /api/v1/erp/balances`**（已确认决策：白名单仅作用于全量接口）。
- 不改内部余额结算逻辑（`CustomerBalance` / 充值 / 消耗链路）。
- 白名单不改变接口的客户过滤语义：停用/删除客户依旧不返回。
- 不做 Excel 模板导入白名单；批量导入仅按 ERP 名单。

## Acceptance Criteria

- [ ] AC1 系统管理出现「余额白名单」菜单/页面，无权限用户不可见、不可访问。
- [ ] AC2 选择 ERP 批量导入：预检展示新增/跳过数量 → 确认后所有该 ERP 有效客户入库，静态余额默认 1000 元。
- [ ] AC3 支持单独搜索并添加单个客户，静态余额默认 1000 元。
- [ ] AC4 可编辑单个客户静态余额；可移出白名单，移出后接口恢复真实余额。
- [ ] AC5 `GET /api/v1/balances`：白名单客户 `balance` 等于其静态余额；非白名单客户 `balance` 等于计算余额；`/api/v1/erp/balances` 行为与改动前一致。
- [ ] AC6 已存在于白名单的客户再次导入/添加时跳过，不覆盖其既有静态余额。
- [ ] AC7 权限 `balance_whitelist:manage` 存在并已授予超级管理员；CI 测试覆盖率 ≥50% 通过。

## Key Decisions

| 决策点 | 结论 | 依据/来源 |
|---|---|---|
| 作用范围 | 仅 `GET /api/v1/balances`，ERP 渠道接口不变 | 用户已确认 |
| 维护能力 | 支持编辑静态余额 + 移出白名单 | 用户已确认 |
| 批量导入 | 按 ERP 批量导入默认 1000 元；已存在客户跳过不覆盖 | 合理默认，避免覆盖人工调整值 |
| 单独添加 | 从现有客户搜索选择，默认 1000 元 | 合理默认，保证 customer_id 存在 |
| 权限 | 新增 `balance_whitelist:manage` | 沿用 `erp_systems:manage` 模式 |
| 静态余额精度 | DECIMAL(12,2)，与 `CustomerBalance` 一致 | 项目既有口径 |
