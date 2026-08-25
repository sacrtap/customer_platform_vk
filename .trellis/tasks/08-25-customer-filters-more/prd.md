# 客户管理筛选器增加更多筛选项

## Goal

在客户管理页面的筛选栏中新增「ERP系统」「合作状态」「结算方式」三个筛选项，默认隐藏，点击"更多"按钮后展开显示。展开后的筛选项折行左对齐排列，"筛选"按钮始终固定在首行右侧。同时新建完整的 ERP 系统管理模块（后端模型+迁移+API+前端页面），作为 ERP 系统筛选选项的数据来源。

## Background

当前 `CustomerFilters.vue` 的筛选栏包含：搜索框、账号类型、行业、规模等级、消费等级、运营经理、销售经理 + 筛选按钮。用户需要更多筛选维度（ERP系统、合作状态、结算方式），但默认不显示以免拥挤。

ERP 系统目前没有独立的管理模块（类似行业类型、合作状态的字典管理），需要新建。现有 `EditCustomerDialog.vue` 中 ERP 系统选项从行业为「房产ERP」的客户列表提取，这种方式不够规范，需要改为从独立的 ERP 系统管理模块获取。

## Confirmed Facts

- 后端 `list_customers` 路由（`backend/app/routes/customers.py:29`）当前支持 `settlement_type` 筛选，但不接收 `erp_system` 和 `cooperation_status` 参数
- 后端 `CustomerService.get_all_customers`（`backend/app/services/customers.py:189`）已有 `settlement_type` 筛选逻辑，没有 `erp_system` 和 `cooperation_status` 的筛选处理
- Customer 模型有 `erp_system`（VARCHAR）、`cooperation_status`（VARCHAR）、`settlement_type`（VARCHAR）字段
- 前端 `getCooperationStatusesList()` API 已存在（`frontend/src/api/cooperationStatuses.ts:5`），返回 `{id, name, value, sort_order}` 列表
- `FilterDropdown` 组件支持 `label`、`modelValue`、`options`、`multiple`、`hideAll` props
- `useCustomerList.ts` 的 `createDefaultFilters` 中已有 `settlement_type: ''`，但没有 `erp_system` 和 `cooperation_status`
- 项目有 `IndustryType` 和 `CooperationStatus` 两个字典管理模块可作参考模板（模型、服务、路由、前端 API、前端页面）
- `BaseModel`（`backend/app/models/base.py:22`）提供 `id`、`created_at`、`updated_at`、`deleted_at` 字段
- 系统管理路由在 `router/index.ts:128-163`，已有 `industry-types` 和 `cooperation-statuses` 页面
- 权限模式：`industry_types:manage`、`cooperation_statuses:manage`，需新增 `erp_systems:manage`
- 侧边栏导航需要添加 ERP 系统入口

## Requirements

### REQ-1: 新建 ERP 系统管理模块（后端）

**模型** (`backend/app/models/erp_system.py`)：
- `ErpSystem` 模型继承 `BaseModel`
- 字段：`name`（VARCHAR(100), unique, not null）、`sort_order`（Integer, default 0）
- 软删除支持（继承 `SoftDeleteMixin`）

**Alembic 迁移**：
- 创建 `erp_systems` 表
- down_revision 指向最新迁移版本

**服务层** (`backend/app/services/erp_system_service.py`)：
- `get_all()` — 获取所有（排除软删除），按 sort_order 排序
- `get_by_id(id)` — 根据 ID 获取
- `get_by_name(name)` — 名称查重
- `create(name, sort_order)` — 创建，名称重复时抛 ValueError
- `update(id, name, sort_order)` — 更新，名称重复时抛 ValueError
- `soft_delete(id)` — 软删除

**路由** (`backend/app/routes/erp_system_routes.py`)：
- `GET /api/v1/erp-systems` — 列表（需 auth_required）
- `POST /api/v1/erp-systems` — 创建（需 `erp_systems:manage` 权限）
- `PUT /api/v1/erp-systems/<id>` — 更新（需 `erp_systems:manage` 权限）
- `DELETE /api/v1/erp-systems/<id>` — 软删除（需 `erp_systems:manage` 权限）

**权限种子数据**：
- 新增 `erp_systems:manage` 权限
- 分配给管理员角色

### REQ-2: 新建 ERP 系统管理模块（前端）

**API** (`frontend/src/api/erpSystems.ts`)：
- `getErpSystemsList()` — GET /erp-systems
- `createErpSystem(data)` — POST /erp-systems
- `updateErpSystem(id, data)` — PUT /erp-systems/:id
- `deleteErpSystem(id)` — DELETE /erp-systems/:id

**类型定义**：
- `ErpSystem` interface：`{ id: number; name: string; sort_order: number; created_at?: string }`

**管理页面** (`frontend/src/views/system/ErpSystems.vue`)：
- 参考 `IndustryTypes.vue` / `CooperationStatuses.vue` 布局
- 表格列：ID、ERP系统名称、排序号、创建时间、操作
- 新增/编辑弹窗：名称（必填）、排序号（必填）
- 删除确认

**路由注册** (`frontend/src/router/index.ts`)：
- 在 system children 中添加 `{ path: 'erp-systems', name: 'ErpSystems', component: ..., meta: { requiresPermission: 'erp_systems:manage' } }`

**侧边栏导航**：
- 在系统管理下添加「ERP系统」入口

### REQ-3: 客户管理筛选器 UI 改造

**CustomerFilters.vue 布局重构**：
- 首行：搜索框 + 基础筛选下拉（账号类型、行业、规模等级、消费等级、运营经理、销售经理）+ "更多"按钮 + "筛选"按钮
- "筛选"按钮固定在首行右侧（使用 `margin-left: auto` 或 flex 布局实现）
- "更多"按钮在筛选按钮左侧
- 点击"更多"展开第二行：ERP系统、合作状态、结算方式，左对齐排列
- 点击"收起"隐藏第二行，保留已选筛选值
- 展开/收起使用 `v-show` 或 `v-if` 控制

**新增筛选选项**：
- ERP系统：`FilterDropdown` 单选，options 从 `getErpSystemsList()` 获取
- 合作状态：`FilterDropdown` 单选，options 从 `getCooperationStatusesList()` 获取
- 结算方式：`FilterDropdown` 单选，options 为 `[预付费=prepaid, 后付费=postpaid]`

**新增 props**：
- `cooperationStatuses: CooperationStatus[]` — 合作状态列表
- `erpSystems: ErpSystem[]` — ERP 系统列表

### REQ-4: 前端数据流改造

**useCustomerList.ts**：
- `Filters` 接口新增 `erp_system: string` 和 `cooperation_status: string`
- `createDefaultFilters` 新增 `erp_system: ''` 和 `cooperation_status: ''`
- `buildParams` 传递这两个新字段
- `handleReset` 重置这两个新字段（已通过 `Object.assign(filters, createDefaultFilters())` 自动覆盖）

**Index.vue**：
- 加载 ERP 系统列表和合作状态列表
- 传递 `erpSystems` 和 `cooperationStatuses` 给 `CustomerFilters`

### REQ-5: 后端筛选支持

**list_customers 路由**：
- 从 query params 接收 `erp_system` 和 `cooperation_status`
- 加入 filters dict

**get_all_customers 服务**：
- 新增 `erp_system` 筛选条件：`Customer.erp_system == erp_system`
- 新增 `cooperation_status` 筛选条件：`Customer.cooperation_status == cooperation_status`

### REQ-6: EditCustomerDialog 同步改造

- ERP 系统选项来源从「行业为房产ERP的客户列表」改为 `getErpSystemsList()`
- 保持 `erp_system` 字段存储 ERP 系统名称（字符串）

## Acceptance Criteria

### ERP 系统管理模块
- [ ] AC-1: 系统管理侧边栏显示「ERP系统」入口
- [ ] AC-2: ERP 系统管理页面可新增/编辑/删除 ERP 系统
- [ ] AC-3: 名称重复时创建/更新返回错误提示
- [ ] AC-4: 删除为软删除，列表不显示已删除项

### 筛选器 UI
- [ ] AC-5: 默认显示基础筛选项 + "更多"按钮，不显示 ERP系统/合作状态/结算方式
- [ ] AC-6: 点击"更多"展开三个新筛选项，折行左对齐显示
- [ ] AC-7: "筛选"按钮在展开/收起状态下都固定在首行右侧
- [ ] AC-8: 点击"收起"后，已选筛选值保留不清空
- [ ] AC-9: 重置按钮清空所有筛选值包括展开区的

### 筛选功能
- [ ] AC-10: 选择 ERP 系统筛选后点筛选，列表正确过滤
- [ ] AC-11: 选择合作状态筛选后点筛选，列表正确过滤
- [ ] AC-12: 选择结算方式筛选后点筛选，列表正确过滤

### EditCustomerDialog
- [ ] AC-13: 编辑客户弹窗中 ERP 系统下拉选项来源为 ERP 系统管理模块

## Out of Scope

- 筛选结果的 URL 持久化（query string 同步）
- 筛选项的 localStorage 记忆展开/收起状态
- 其他页面（消耗分析、回款分析、余额管理）的筛选器改造
- ERP 系统与客户的关联改为外键（当前 `erp_system` 是字符串字段，保持不变）
- 数据迁移（将现有客户 `erp_system` 字符串值关联到新 ERP 系统记录）
