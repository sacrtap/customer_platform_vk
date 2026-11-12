# CRM 充值管理 — 技术设计

权威细节：`docs/specs/2026-11-11-crm-recharge-management-plan.md`（PLAN）。本文件固化实现时的契约边界与不变量。

## 架构边界

```
CRM 开放 API (只读)
   ↑ CrmClient（限流/鉴权/分页）
CrmRechargeService ──→ crm_customers / crm_payments / crm_sync_runs（镜像）
   │
   ├─ 绑定：Customer.crm_customer_id（唯一部分索引，软删除不占位）
   └─ 导入：BalanceService.recharge（事务内记账）→ recharge_records（recharge_date + crm_payment_id UNIQUE）
```

- 镜像 upsert 用短事务；HTTP 不在事务内；活跃 session 不跨协程共享。
- 同步永不修改 `RechargeRecord` / `CustomerBalance`。
- 导入是唯一资金写入点，唯一约束 `crm_payment_id` 是最终防线。

## 数据模型

`crm_customers`：`corp_id VARCHAR(64) NOT NULL`、`external_id BIGINT NOT NULL`、`name`、`normalized_name`、`owner_name NULL`、`last_seen_at`；UNIQUE`(corp_id, external_id)`。

`crm_payments`：`corp_id`、`external_id BIGINT`、`crm_customer_id FK crm_customers.id NULL`、`contract_external_id`、`contract_title`、`customer_external_id`、`customer_name`、`amount NUMERIC(12,2) NULL`、`receive_date DATE NULL`、`approve_status VARCHAR(32)`、`industry_path TEXT`、`industry_label TEXT`、`source_updated_at`、`eligible BOOL`、`blocked_reason TEXT`、`last_seen_at`、`imported_snapshot JSONB NULL`、`source_changed BOOL DEFAULT false`；UNIQUE`(corp_id, external_id)`；索引 `(receive_date, eligible)`、`crm_customer_id`。

`crm_sync_runs`：`corp_id`、`month DATE（月首）`、`trigger(scheduled|manual)`、`operator_id NULL`、`status(pending|running|succeeded|failed)`、`phase(customers|contracts|payments|completed)`、`heartbeat_at`、`started_at`、`finished_at`、`customer_count`、`contract_count`、`scanned_contract_count`、`payment_count`、`eligible_count`、`error_message`；部分唯一 `uq_crm_sync_active_corp(corp_id) WHERE status IN ('pending','running')`。

`customers.crm_customer_id INTEGER NULL FK crm_customers.id`；部分唯一 `uq_customer_active_crm_binding(crm_customer_id) WHERE deleted_at IS NULL AND crm_customer_id IS NOT NULL`。

`recharge_records.recharge_date DATE NOT NULL`（服务端默认 `CURRENT_DATE`）、`crm_payment_id INTEGER NULL FK crm_payments.id UNIQUE`。唯一约束覆盖软删除行。

迁移：单 revision，先建表 → 客户 FK → 新列 nullable → `UPDATE recharge_records SET recharge_date = created_at::date` → NOT NULL + 默认。不覆盖任何历史 created_at/余额/金额。

## 配置

`Settings`: `crm_enabled=False`、`crm_base_url="https://lxcrm.weiwenjia.com"`、`crm_corp_id`、`crm_phone`、`crm_password`（str，默认空）。仅允许官方 HTTPS 域名（校验 host 白名单），不接受请求体指定 host。

## CrmClient 契约

- 认证 `POST /api/v2/auth/login`，`{device: 'open_api', login: phone, password, corp_id}`；校验 `code==0`、`data.user_token` 非空、corp 一致、`is_expired != true`。
- Header `Authorization: Token token=<token>, device=open_api, version_code=9.9.9`。
- HTTP 200 + `code!=0` = 失败，不当空列表。
- Redis 企业级限流 `crm:rate:{corp_id}` SET NX PX=1250；Redis 不可用 → 拒绝发起外部请求。
- Token 缓存 `crm:token:{corp_id}`（`_ttl_config['crm_token']=1800`）；登录锁 `crm:login:{corp_id}` owner 释放，TTL 60s。
- 401/100401 最多刷新 token 重放一次 GET。
- 分页：`per_page=100`、`page` 递增、`sort=created_at&order=asc`；以 `has_next_page` / `total_count` / 空页收敛；重复页或提前空页 = 失败。
- 接口：`/custom_fields/customer/by_group`、`/custom_fields/received_payment/by_group`、`/customers`、`/contracts`、`/contracts/{id}/received_payments`、`/customers/{id}`、`/contracts/{cid}/received_payments/{pid}`。
- 日志禁止记录 body / token / Authorization / 完整响应。

## 同步契约

- `create_sync_run`：先把 heartbeat>2min 的 pending/running 置 failed；插入 pending；活跃唯一冲突 → 409。返回后以 Sanic 后台任务启动 `execute_sync_run`。
- `execute_sync_run`：原子 `UPDATE ... WHERE status='pending' RETURNING` 领取 running；每 30s 独立短事务 heartbeat；每次写进度前确认仍是 running。
- 顺序：客户全量分页镜像 → 合同全量分页 → 逐合同回款分页 → 本地按 `receive_date` 月窗口 + `approve_status='approved'` 过滤 → 候选与已镜像状态变更记录读取详情 → 行业/金额/日期校验 → upsert 镜像。
- 行业元数据：label='行业分类' 的字段名必须等于 `text_asset_3565dc`；根值 房产经纪 `ba2503bf-...`、新房开发 `bdb440d1-...`；递归收集后代。解析支持字符串与数组，按 `/` 分段；未知结构 → blocked_reason，禁止导入。
- eligible：行业命中 + 同企业 + customer/contract ID 有效 + 金额有限正数、≤2 位小数、不超 NUMERIC(12,2) + 日期有效 + approved。
- 已导入行记录 `imported_snapshot` 白名单，与新详情比较 → `source_changed=true`，不自动改账。
- 本次扫描未见到的既有镜像：GET 原合同下详情复核；404 → 不可用 + 已导入 source_changed=true。
- 全部分页成功才 succeeded；任何网络/授权/分页/解析失败 → failed + 进度保留。

## API 契约（`/api/v1/crm-recharge`）

| 端点 | 关键点 | 权限 |
|---|---|---|
| `GET /customers/candidates` | `customer_id` 必需；query 可选；page/page_size(≤50)；返回 list/total/page/page_size/directory_updated_at | customers:edit + customers:crm_bind |
| `PUT /customers/<id>/binding` | body `{crm_customer_id: number\|null}`；非法非空类型 400；幂等同值成功；冲突 409 | customers:edit + customers:crm_bind |
| `GET /payments` | month/keyword/status(pending\|imported\|blocked\|all)/page/page_size(≤100)；行级可见性 | crm_recharge:view |
| `GET /payments/<id>` | 本地镜像详情，不返回原始 JSON | crm_recharge:view |
| `POST /sync-runs` | `{month:'YYYY-MM'}` → 202 `{id,status:'pending'}`；冲突 409 含 run_id | crm_recharge:sync + customers:view_all |
| `GET /sync-runs` | month 可选；含 latest_success_at | crm_recharge:sync + customers:view_all |
| `POST /payments/<id>/import` | `{customer_id, real_amount, bonus_amount}` 十进制定点字符串；返回 recharge_record_id/金额/日期/balance/already_imported | crm_recharge:import + billing:recharge |

错误映射：403 FORBIDDEN、404 NOT_FOUND、400/409 BAD_REQUEST、上游失败 502 SERVICE_ERROR、未配置/Redis 不可用 503 SERVICE_ERROR。

评分：NFKC → casefold → 去空白与标点；完全相等 1.0；包含 `0.8+0.19*min/max`；其余 `difflib.SequenceMatcher(autojunk=False).ratio()*0.79`；阈值 0.35；score 降序、external_id 升序；top10；空规范名 → 空列表。

行级可见性：有 `customers:view_all` 看全部；否则 INNER JOIN 当前绑定 Customer 且 `manager_id==uid OR sales_manager_id==uid`；已导入行按 `RechargeRecord.customer_id` 判定归属。

## 资金原子性契约

`BalanceService.recharge(..., *, recharge_date=None, crm_payment_id=None)` 改为**无 commit** 的事务内记账：

1. 调用方必须已在 `db_session.begin()` 内，否则拒绝（不私自 commit）。
2. 锁序：`Customer FOR UPDATE` → 余额行。
3. 余额行：`INSERT ... ON CONFLICT (customer_id) DO NOTHING` → `SELECT ... FOR UPDATE`（populate_existing）。
4. 金额 Decimal；校验 NUMERIC(12,2) 溢出。
5. 软删除余额行：非零历史余额 → 拒绝；全零 → 恢复 `deleted_at=None`。
6. 手动/Excel 保留允许负值与赠金语义；CRM 侧由导入校验保证实充=源金额>0、赠送≥0、不同时 0。

调用迁移：`routes/billing/balances.py::recharge`、`routes/billing/imports.py::import_balance`（`batch_import_recharge` 改为逐行 PL 调用 + savepoint），审计 `create_audit_entry(auto_commit=False)` 同事务。

业务日期读点：`balances.py` 最近充值/本月统计/排序/导出、`analytics.py::get_balance_trend`、`invoice_excel.py::_query_balance_info`、`billing.py::get_recharge_records` 响应补 `recharge_date`/`crm_payment_id`/`crm_payment_external_id`（排序仍按 created_at）。

`clear_balance_data`：事务内先 `LOCK TABLE customers IN EXCLUSIVE MODE`，若存在任何 `crm_payment_id IS NOT NULL` 的充值记录（含软删）→ 409「存在CRM导入记录，不能清除入账凭据」。

## 权限码

新增 4 码：`customers:crm_bind`(customers)、`crm_recharge:view`、`crm_recharge:sync`、`crm_recharge:import`(crm_recharge)。同步 `tests/_test_data.py::PERMISSION_ROWS`、前端 `permissionGroups.ts` MODULE_NAME_MAP/MODULE_ORDER。上线用 `seed.py --sync-permissions`。

## 前端契约

- `frontend/src/api/crmRecharge.ts` + 类型；`views/system/CrmRecharge.vue`（路由 `/system/crm-recharge`，`meta.requiresPermission='crm_recharge:view'`；导航需同时更新 `AppSidebar.vue` 与 `useAppLayout.ts::navSections`）。
- `views/customers/components/CrmCustomerBinding.vue`（props `{customerId}`）：300ms 防抖 + 请求序号丢弃乱序；推荐 top10；确认后独立保存；无 `crm_recharge` 无关权限仅展示已有绑定。
- `RechargeRecordModal.vue` 展示「实际充值日期 / 创建时间 / 来源」；`BalanceTable.vue` 与 `useBalance.ts` 标签改「充值日期」，按自然日算天数（不 `new Date` 转 UTC）。

## 兼容与回滚

- `CRM_ENABLED=false`：不注册自动任务；手动同步/新绑定上游校验/首次导入返回 503；已有镜像与已导入记录可查，解绑不依赖 CRM；同源已导入幂等查询仍返回原结果。
- 有 CRM 已入账数据时不做生产 downgrade；停用同步并保留表与资金记录。
