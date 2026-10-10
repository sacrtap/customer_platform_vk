# PRD: 开放平台「获取所有客户余额」接口

## 1. 背景

开放平台目前仅提供 `GET /api/v1/erp/balances`（按 ERP 渠道查询下游客户余额）。外部合作方存在一次获取**全部客户余额** 的场景。该能力从业务分类上不属于 ERP 渠道域，因此新接口路径应与 `erp` 平级，而非挂在 `/api/v1/erp/` 下。

## 2. 目标

1. 新增开放平台接口 `GET /api/v1/balances`，通过 API-Key 认证，返回全部**有效客户**（未删除、未停用，不限 ERP 渠道）的客户 ID、名称与当前可用余额。
2. 扩展认证中间件，使 `/api/v1/balances` 路径走 API-Key 认证（而非 JWT）。
3. 补充开放平台 VitePress 文档：新接口文档页 + 接口索引 + sidebar + 变更日志。
4. 为开放平台接口补齐集成测试（此前 `/api/v1/erp/balances` 无测试）。
5. 不改动现有 `/api/v1/erp/balances` 的语义（`erp_channel` 仍必填），保持向后兼容。

## 3. 功能需求

### 3.1 接口规范

- **方法 / 路径**: `GET /api/v1/balances`
- **认证**: 必填（`Authorization: Bearer {api_key}`），失败返回 `40104` / `40105`
- **参数**: 无
- **响应**: `{ code, message, data }`，`code = 0` 表示成功
- **data 项**:
  - `customer_id`: string — 客户在 ERP 系统中的企业 ID（company_id）
  - `customer_name`: string — 客户名称（企业全称）
  - `balance`: number — 当前可用余额（总金额 - 已用金额，保留两位小数）
- **data 排序**: 按 `customer_id`（company_id）升序，与既有渠道接口一致
- **口径**: 全部未删除（`deleted_at IS NULL`）、未停用（`is_disabled IS NOT TRUE`）的客户，**包含** `erp_system` 为空或为 `noerp`（无 ERP）的客户；无余额记录的客户 `balance = 0.0`

### 3.2 认证改造

`backend/app/middleware/auth.py` 中 API-Key 认证前缀 `OPENAPI_PREFIX = "/api/v1/erp/"` 需扩展为多前缀，覆盖 `/api/v1/balances`，否则新接口会落入 JWT 认证分支。

### 3.3 文档

- 新增 `openapi-docs/docs/api-reference/all-balances.md`：接口信息、请求/响应参数、curl 与 Python 示例、错误码、与渠道版接口的差异说明。
- `index.md` 接口索引新增一行；`config.ts` sidebar 新增条目；`changelog.md` 新增记录。

## 4. 非目标（边界）

- 不改动 `/api/v1/erp/balances` 现有语义与响应。
- 不新增分页 / limit 参数（与现有开放平台接口保持一致，数据量大可后续迭代）。
- 不涉及前端页面改动、不新增数据库字段 / 迁移。
- 不重构文档站工程结构。

## 5. 验收标准

1. 有效 API-Key 请求 `GET /api/v1/balances` 返回 `{code: 0, message: "success", data: [...]}`，包含多渠道与无 ERP 客户、无余额客户 balance 为 0.0、按 company_id 升序。
2. 软删除 / 停用客户不出现在结果中。
3. 缺少 / 无效 API-Key 返回 401（`40104`）；已过期返回 `40105`。
4. 现有接口 `GET /api/v1/erp/balances?erp_channel=xxx` 行为不变（回归测试通过）。
5. 集成测试新增覆盖通过；`ruff check`、`pyright` 无错误；全量覆盖率口径 ≥50%（CI gate）。
6. `cd openapi-docs && npm run docs:build` 构建成功，新接口文档页可访问，索引 / sidebar / changelog 已更新。
