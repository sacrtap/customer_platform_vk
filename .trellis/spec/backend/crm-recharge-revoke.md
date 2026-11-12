# CRM 充值导入的撤销契约

> 场景：中台客户绑定了错误的 CRM 客户，随后该 CRM 回款被导入成充值。余额进了错客户，
> 且该回款被「已导入」锁死。本文定义唯一合法的回滚路径。
>
> 实现：`app/services/crm_recharge.py::CrmRechargeImportService.revoke_import`、
> `app/routes/crm_recharge.py::revoke_crm_import`（2026-11-12）

## 为什么不能靠软删/改绑

| 尝试 | 为什么不行 |
|---|---|
| 软删充值记录 | `recharge_records.crm_payment_id` 是 **UNIQUE 且覆盖软删除行**；软删后该回款仍判定「已导入」，永远无法重新导入 |
| 只改绑定关系 | `bind()` 只改 `customers.crm_customer_id`；已入账余额与充值凭据不会迁移，旧记录永久挂在错客户 |
| 冲正成负数充值 | 唯一键按「回款维度」设计，冲正记录仍占用 `crm_payment_id`，同样无法重新导入 |

因此撤销只能：**扣回余额 + 物理删除充值记录 + 释放回款**，审计留痕由 `audit_logs` 承担。

## 接口与权限

```
POST /api/v1/crm-recharge/payments/<payment_id>/import/revoke
body: {"customer_id": <扣款客户>, "reason": "<必填，≤500字>", "force": false}
权限: crm_recharge:revoke + billing:recharge（仅超级管理员预授）
```

## 语义

1. **锁序**：客户 → 回款 → 充值记录 → 余额行（与导入一致，避免死锁）。
2. **校验**：记录存在且 `crm_payment_id` 非空；`record.customer_id == customer_id`。
   注意**不**校验当前绑定关系 —— 撤销针对「钱在谁账上」，绑定是另一个事实。
3. **余额充足**：`balance.real >= record.real` 且 `bonus >= record.bonus` → 直接扣回。
4. **余额不足（资金已被消耗）**：
   - 非超级管理员 → `403`；
   - 超级管理员必须显式 `force=true`，否则 `409`；
   - 执行后余额**允许为负**（表示欠款），结果与审计带
     `needs_manual_reconciliation=true`、`shortfall_real/bonus`。
5. **释放回款**：`imported_snapshot = NULL`、`source_changed = false`。
6. **不改绑定**。

## 正确操作顺序

```
① 撤销导入（余额扣回、回款回到待导入）
② 改绑客户（错的客户解绑 → 正确客户绑定该 CRM 客户）
③ 重新导入（重新确认实充/赠送，生成新充值记录与审计）
```

## 改绑护栏（硬阻断）

`CrmCustomerBindingService.bind()` 在解绑或改绑前检查该客户是否存在
`crm_payment_id IS NOT NULL` 的充值记录（含软删），存在则 `409`
「该客户已有CRM充值导入记录，请先撤销导入再修改绑定」。

## 审计

`audit_logs.action = crm_recharge_import_revoke`，`changes` 含：原因、源回款 ID、
金额、`forced`、`needs_manual_reconciliation`、`shortfall_*`、`balance_before/after`。
充值记录物理删除后，这份快照是唯一的资金留痕，不得裁剪字段。

## 存量库权限补丁

```bash
cd backend && .venv/bin/python scripts/fix_add_crm_revoke_permission.py   # 幂等，并失效权限缓存
```
