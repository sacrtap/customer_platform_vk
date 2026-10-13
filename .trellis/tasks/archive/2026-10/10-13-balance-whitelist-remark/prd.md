# 余额白名单备注列与编辑备注

## Goal

在「余额白名单」页面（系统管理 → `/system/balance-whitelist`）新增「备注」列展示；并在「编辑余额」弹窗中支持填写、修改、清空备注并提交落库。用户价值：运维人员可为每条白名单静态余额记录补充业务说明（如「临时调额、到期日」），便于识别与审计。

## Background（已确认事实，来自代码证据）

- 现有页面 `frontend/src/views/system/BalanceWhitelist.vue`：列表 `columns` 含 ID/客户ID/客户名称/ERP/静态余额/添加时间/操作；「编辑余额」弹窗仅有静态余额字段，提交调用 `updateBalanceWhitelist(id, static_balance)`。
- 前端类型 `frontend/src/types/index.ts:261` `BalanceWhitelistItem` 无备注字段；API 层 `frontend/src/api/balanceWhitelist.ts` 的 `updateBalanceWhitelist(id, static_balance)` 只透传余额。
- 后端模型 `backend/app/models/balance_whitelist.py` 仅 `customer_id` / `static_balance`，无备注列。
- 服务 `backend/app/services/balance_whitelist_service.py`：`get_all()` 以显式列 `select(...)` 组 dict 返回；`update(id, static_balance)` 仅改余额；`_validate_balance()` 做余额校验。
- 路由 `backend/app/routes/balance_whitelist_routes.py`：`PUT /<id:int>` 只解析 `static_balance`（缺失 → `MISSING_PARAMETER`）。
- 迁移链 head = `w2x3y4z5a6b7`；`balance_whitelists` 由 `v1w2x3y4z5a6` 建表。测试库按 ORM metadata 自动补齐缺失列（`6f53fe5`），故测试不依赖新迁移。
- 集成测试 `backend/tests/integration/test_balance_whitelist_routes.py` 覆盖列表/新增/编辑/删除/权限；`_insert_whitelist` 帮助函数按显式列插入。

## Requirements

- **R1 列表备注列**：`GET /api/v1/balance-whitelists` 返回的每个 item 增加 `remark` 字段（无备注为 `null`）；页面表格新增「备注」列展示该值。
- **R2 编辑弹窗填写备注**：「编辑余额」弹窗新增备注输入项；打开时以该记录当前 `remark` 回填，允许修改或清空。
- **R3 提交备注**：`PUT /api/v1/balance-whitelists/<id>` 接受可选 `remark`，与 `static_balance` 一并保存（同一事务）。
- **R4 备注约束**：可选（非必填）；最长 200 字符；提交空串/空白/`null` 时存为 `NULL`（清空语义）。超长 → 400。
- **R5 兼容性**：未传 `remark` 的 PUT 请求（旧调用）行为不变，仅更新余额；列表其余字段与响应结构（`code`/`message`/`data`/`meta`）不变。

### 边界（Out of Scope）

- 不改「添加客户」弹窗（用户明确仅要求编辑弹窗）。
- 不改开放平台 `GET /api/v1/balances` 接口行为（备注仅用于管理页展示）。
- 不改批量导入逻辑（导入不写备注，保持默认 `NULL`）。
- 不做备注的搜索/筛选（列表 keyword 仍仅按客户名/公司ID）。

## Acceptance Criteria

- [ ] AC1 `GET /api/v1/balance-whitelists` 列表项包含 `remark` 字段：有备注返回字符串，无备注返回 `null`。
- [ ] AC2 页面白名单表格出现「备注」列并正确展示备注内容（空备注显示为空/占位）。
- [ ] AC3 打开「编辑余额」弹窗时备注输入回填该记录当前值；可修改后提交，刷新列表可见新备注。
- [ ] AC4 将备注清空（空串/空白）提交后，接口返回并展示 `null`。
- [ ] AC5 `PUT` 仅传 `static_balance`（不传 `remark`）时，备注保持不变；余额更新成功。
- [ ] AC6 备注超过 200 字符的提交 → 400，错误信息明确。
- [ ] AC7 集成测试新增/更新备注用例通过；CI 测试覆盖率 ≥50% 门禁通过。

## Key Decisions

| 决策点 | 结论 | 依据/来源 |
|---|---|---|
| 填写入口 | 仅「编辑余额」弹窗 | 用户确认 |
| 必填性 | 可选、非必填 | 用户确认 |
| 长度上限 | 200 字符 | 用户确认；与充值 remark 200 截断口径一致 |
| 清空语义 | 空串/空白/`null` → 存 `NULL` | 用户确认（可清空）|
| 存储类型 | `String(200)` nullable | 与 200 上限一致，避免 Text 无限长 |
| PUT 缺省语义 | 未传 `remark` 键 → 不改备注 | 向后兼容旧调用 |
| 迁移 | 新增 alembic 迁移，`down_revision=w2x3y4z5a6b7` | 迁移链 head 约定 |

## Open Questions

（无）
