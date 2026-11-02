# Design：VR编辑费用结算模块

## 架构与边界

完全复用 Invoice 模块分层，不引入新机制：

```
routes/billing/vr_settlements.py   ← HTTP 层（13 端点，照抄 invoices.py 模式）
        ↓
services/vr_settlement.py         ← VrSettlementService（状态机 + 编排）
        ↓
services/billing.py               ← BalanceService.consume（唯一扣款入口，零改动除新增 kwarg）
models/vr_settlement.py           ← VrSettlement / VrSettlementDiscountHistory
models/billing.py                 ← ConsumptionRecord 加 vr_settlement_id 一列
```

前端同构：`api/vrSettlement.ts` → `composables/useVrSettlement.ts` → `views/billing/VrSettlements.vue` + 4 组件。

## 数据模型

### vr_settlements

| 列 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | BaseModel 提供 |
| settlement_no | String(50) unique index | `VR-YYYYMMDD-<customer_id>-XXXX` |
| customer_id | Integer FK customers.id index | 结算客户 |
| period_start / period_end | DateTime(tz) NOT NULL index | 结算周期（UTC 存储，路由层 `local_date_range_to_utc` 转换） |
| total_amount | DECIMAL(12,2) NOT NULL | 结算金额（表单填写） |
| discount_amount | DECIMAL(12,2) default 0 | 减免金额（可负=加价） |
| discount_reason / discount_attachment | Text / String(255) | 减免原因/附件路径 |
| status | String(30) index default 'draft' | `pending_sales_supervisor` 26 字符，需 30 |
| discount_applied_at / discount_approver_id / discount_approved_at / discount_approval_comment | String(50)/Int FK/… | 减免申请与一并审批 |
| cs_supervisor_confirmed_by/at、sales_confirmed_by/at、sales_supervisor_confirmed_by/at | Int FK / String(50) | 三级审批追踪 |
| customer_confirmed_at/by、completed_at/by、cancelled_at/by | … | 终态追踪 |
| detail_file_path / detail_file_name | String(255) | 明细 Excel（仅存档+下载） |
| is_auto_generated | Boolean default False | 恒 False（自动创建待开发） |
| created_by | Int FK users.id | 创建人 |
| created_at/updated_at/deleted_at | BaseModel | 软删除 |

`final_amount = total_amount - (discount_amount or 0)` 为计算字段，不落库（与 Invoice 一致）。

索引：`idx_vr_settlement_customer_period(customer_id, period_start, period_end)`、`idx_vr_settlement_status_period(status, period_start)`。

### vr_settlement_discount_histories

照抄 `InvoiceDiscountHistory`：settlement_id（FK CASCADE）/ discount_amount / discount_reason / discount_attachment / applied_at / applied_by + 索引 `idx_vr_discount_history_settlement(settlement_id, applied_at)`。

### consumption_records 加列

`vr_settlement_id Integer FK vr_settlements.id NULL index`。VR 扣款产生的消耗记录 `invoice_id=NULL, vr_settlement_id=<id>`；既有 Invoice 扣款 `vr_settlement_id=NULL`。两列独立可空，互不影响。

## 数据流

### 创建（端点 3）

```
POST {customer_id, period_start, period_end, total_amount, detail_file_path, detail_file_name}
  → 校验（customer 存在 404 / scope 403 / 金额>0 / 日期格式）
  → local_date_range_to_utc(start, end)  → UTC datetimes
  → service.create_settlement() → settlement_no=VR-{cst_today}-{cid}-{rand4}
  → 201 {id, settlement_no, total_amount}
```

### 审批流与扣款（端点 4-11）

```
submit(draft)            → 校验 customer.sales_manager_id 非空 → pending_cs_supervisor
confirm-cs               → pending_sales
confirm-sales            → 身份校验 sales_manager_id == user_id → pending_sales_supervisor
confirm-sales-supervisor → 若 discount_amount≠0 写审批三字段 → pending_customer
reject-sales-supervisor  → comment 必填 → 回 pending_sales
confirm(customer)        → commit customer_confirmed → _execute_deduction:
                             final = total - discount
                             BalanceService(BalanceRepository(db)).consume(
                                 customer_id=settlement.customer_id,   # 自身余额，非代扣
                                 amount=final,
                                 vr_settlement_id=settlement.id)
                             成功 → completed + completed_at/by
                             失败 → 保持 customer_confirmed，(False, "客户确认成功，但扣款失败：…")
retry-deduction          → customer_confirmed 时重跑 _execute_deduction
cancel                   → 非终态 → cancelled
```

### 关键契约

1. **事务边界**：`consume` 内部自行收敛事务（`in_transaction()` 时先 commit，再 `db.begin()` + `with_for_update()` 行级锁 + tenacity 3 次重试）。`confirm_customer` 先 commit 状态再调扣款，与 Invoice 完全一致。
2. **时区**：所有 `*_at` 字符串列用 `cst_now().strftime("%Y-%m-%d %H:%M:%S")`（CST 墙钟）；周期用 `local_date_range_to_utc` 入库 UTC；列表返回时前端 `formatDateTime` 展示（沿用现有约定）。
3. **数据可见性**：`mine_user_id` = `customer_scope_user_id(request)`（无 `customers:view_all` 时为当前用户 id），列表过滤 `or_(Customer.manager_id, Customer.sales_manager_id)`；单详情 `_ensure_settlement_scope` 403。
4. **审计**：8 个动作端点手动审计（before/after 状态快照，`record_type="vr_settlement"`，`module="billing"`）；中间件跳过块按路径后缀精确跳过这 8 个动作端点，避免双写。创建/减免/删除走中间件自动审计。
5. **缓存**：所有成功变更后 `cache_service.invalidate_billing_cache()`。

## 兼容性与迁移

- 迁移 `d0e1f2a3b4c5`，down_revision `c9d0e1f2a3b4`（已核实为当前 head 且新 id 未占用）。
- 权限插入幂等（`ON CONFLICT (code) DO NOTHING` + 超管关联 `NOT EXISTS`），downgrade 完整逆序。
- `ConsumptionRecord.consume` 新增 kwarg `vr_settlement_id: Optional[int] = None`，默认 None → 既有 Invoice 调用方零改动；`ConsumptionRecord(...)` 构造多传一个可空列，既有测试不受影响。
- 前端为新路由/新页面，无既有契约破坏；`permissionGroups` 的 `MODULE_ORDER` 插入位置仅影响角色页卡片排序。

## 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 扣减对象 | 客户自身余额 | 需求未提及代扣；Invoice 的 settlement_account 是另一产品机制，不引入 |
| 减免审批形态 | 销售主管节点一并审批（单端点） | 需求明确「通过=节点通过且减免生效；驳回=整单退回」；无需独立 discount_approved 布尔拆分 |
| 驳回语义 | 整单退回 pending_sales | 需求明确；减免保留待重新一并审批 |
| 状态机独立于 Invoice | 新枚举/新表 | 客服主管节点 + 销售主管节点 + 无 ops 节点，与 Invoice 五态流程不同构；共用表加类型列会增加大量分支 |
| service 构造 | `__init__(self, db: AsyncSession)` 直接用 db | 不涉及 repository 协议分层（无 pricing_repo 依赖），比 InvoiceService 的双 repo 构造更简 |
| discount_history 排序 | applied_at desc | 与现有 invoice 详情路由一致（最新在上） |
| retry_deduction 失败消息 | 去掉「客户确认成功」前缀，返回「扣款失败：…」 | 与 InvoiceService.retry_deduction 现有约定一致 |

## 回滚

- 迁移 downgrade：删 role_permissions 关联 → 删 8 permissions → drop idx+column → drop 两表（逆序完整）。
- 代码回滚：git revert；`consume` 的 kwarg 有默认值，回滚路由/service 不影响既有结算单功能。
