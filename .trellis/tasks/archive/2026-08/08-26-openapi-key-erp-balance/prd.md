# PRD: 开放平台 API-Key 管理与 ERP 余额查询接口

## 1. 背景

当前系统的 API 接口仅支持通过 JWT Token（用户登录态）进行访问，无法安全地向外部 ERP 系统开放数据接口。需要建设开放平台能力，允许外部系统通过 API-Key 认证方式调用指定的开放接口，首先支持「获取 ERP 渠道下游客户余额」场景。

## 2. 目标

1. **API-Key 管理**：在系统管理下新增「API-Key」模块，支持 API-Key 的申请（创建）、查看、停用/启用、删除。
2. **开放平台 API**：实现 `GET /api/v1/erp/balances` 接口，通过 API-Key 认证，返回指定 ERP 渠道下所有企业的客户ID、客户名称和当前余额。
3. **API 指南文档**：在前端提供 `/openapi` 路由的 API 接口文档页面。

## 3. 功能需求

### 3.1 API-Key 管理（前端 + 后端）

#### 后端
- 新增 `ApiKey` 数据模型，字段包括：名称、Key 值（自动生成）、状态（active/disabled）、创建人、过期时间（可选）、最后使用时间、描述。
- 新增 `api_keys:manage` 权限，加入 seed.py 权限定义。
- 新增 API-Key 管理路由（`/api/v1/api-keys`），支持：
  - `GET` 列表查询（分页）
  - `POST` 创建 API-Key（返回明文 Key，此后不再展示完整 Key）
  - `DELETE` 删除 API-Key（软删除）
  - `PATCH /<id>/toggle-status` 启用/停用切换

#### 前端
- 系统管理侧边栏新增「API-Key」菜单项，权限 `api_keys:manage`。
- 新增 `ApiKeyManagement.vue` 页面：
  - 列表展示：名称、Key（脱敏显示，仅前8位 + ****）、状态、创建时间、最后使用时间。
  - 创建弹窗：名称 + 描述 + 可选过期时间，创建成功后弹窗显示完整 Key 供一次性复制。
  - 操作：启用/停用切换、删除。

### 3.2 开放平台 API：ERP 渠道客户余额查询

#### 接口规范
- **请求方法**: `GET`
- **请求路径**: `/api/v1/erp/balances`
- **认证方式**: API-Key（通过 `Authorization: Bearer {api_key}` 传递）
- **关键参数**: `erp_channel` (query string) — ERP 渠道编码，如 `qiaofang`
- **响应格式**:

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {"customer_id": "615", "customer_name": "北京金诚阜业房地产经纪有限公司", "balance": 100000.00},
    {"customer_id": "1552", "customer_name": "荣城地产", "balance": 0.00}
  ]
}
```

#### 后端实现
- 在 `auth_middleware` 中增加对 `/api/v1/erp/` 前缀路径的 API-Key 认证支持：
  - 当请求路径以 `/api/v1/erp/` 开头时，使用 API-Key 认证而非 JWT Token 认证。
  - 从 `Authorization: Bearer {key}` 提取 Key，查询 `api_keys` 表验证有效性（状态为 active 且未过期）。
  - 认证通过后将 API-Key 信息存入 `request.ctx`。
  - 更新 `last_used_at` 字段。
- 新增 `openapi_bp` Blueprint（`/api/v1/erp`），实现 `GET /balances` 路由：
  - 参数校验：`erp_channel` 必填。
  - 查询 `customers` 表中 `erp_system = erp_channel` 且未删除、未停用的客户。
  - 关联 `customer_balances` 表获取余额（`total_amount - used_total`）。
  - 返回 `customer_id`（company_id 字符串）、`customer_name`（name 字段）、`balance`（可用余额）。

### 3.3 API 指南文档页面

#### 前端
- 新增 `/openapi` 路由，不需要登录认证（`meta: { public: true }`）。
- 新增 `OpenApiGuide.vue` 页面，内容包括：
  - 概述：开放平台简介。
  - 认证方式：API-Key 申请流程、请求头格式说明。
  - 接口列表：ERP 余额查询接口的详细说明（路径、方法、参数、响应示例）。
  - 错误码说明。
- 页面样式遵循现有设计系统（Arco Design + 深色侧边栏 / 浅色内容区）。

## 4. 约束

- API-Key 在创建时仅展示一次完整明文，后续列表中脱敏显示。
- 开放平台 API 路径 (`/api/v1/erp/`) 不走 JWT 认证，走 API-Key 认证。
- API-Key 认证中间件需跳过 JWT 验证逻辑，不与 Token 黑名单交互。
- 前端 `/openapi` 页面为公开页面，不需要登录认证。
- 响应格式遵循现有 `{code, message, data}` 结构。
- `customer_id` 返回 `company_id` 字段的字符串值（与外部 ERP 系统对接）。
- `balance` 返回可用余额（`total_amount - used_total`），保留两位小数。

## 5. 验收标准

1. 系统管理菜单下出现「API-Key」菜单项，可创建/查看/停用/删除 API-Key。
2. 创建 API-Key 时展示完整 Key，列表中 Key 脱敏显示。
3. 使用有效 API-Key 请求 `GET /api/v1/erp/balances?erp_channel=qiaofang` 返回正确数据。
4. 使用无效/停用/过期的 API-Key 请求返回 401。
5. 缺少 `erp_channel` 参数返回参数错误。
6. 前端 `/openapi` 页面可公开访问，展示完整的接口文档。
7. 后端 lint 通过：`cd backend && ruff check app/`。
8. 前端 type-check 通过：`cd frontend && pnpm type-check`。
