# 余额充值记录撤销（技术设计）

## 现状约束（决定设计）

| 事实 | 出处 |
|---|---|
| 余额池化，`recharge_records` 与 `consumption_records` 无关联字段 | 只能以「当前余额够不够扣」判定 |
| 手动/Excel 充值 `crm_payment_id IS NULL`，PG 唯一约束不约束 NULL → 软删安全 | `models/billing.py:90` |
| CRM 来源充值唯一键覆盖软删 → 不能软删，必须在 CRM 页撤销（那边还要释放回款） | `models/billing.py:89` |
| 充值记录列表已过滤软删 | `services/billing.py::get_recharge_records` |
| 两处统计**未**过滤软删：结算单当月充值、充值趋势/历史累计 | `services/invoice_excel.py:275`、`services/analytics.py:2414/2464` |

## 接口

```
POST /api/v1/billing/recharge-records/<record_id>/revoke
body: {"reason": "<必填，≤500>", "force": false}
权限: billing:recharge_revoke (新增) + billing:view
```

返回：
```json
{"code": 0, "message": "已撤销充值记录",
 "data": {"recharge_record_id": 1, "customer_id": 7,
          "real_amount": "1000.00", "bonus_amount": "200.00",
          "needs_manual_reconciliation": false,
          "shortfall_real": "0.00", "shortfall_bonus": "0.00",
          "balance": {"real_amount": "...", "bonus_amount": "...", "total_amount": "..."}}}
```

## 服务层

`BalanceService.revoke_recharge(...)`（`app/services/billing.py`），事务内调用：

1. 锁序与 `recharge` 一致：`Customer → 余额行 → RechargeRecord`。
2. 校验：
   - 客户存在且未软删；数据可见性（`scope_user_id`）；
   - 记录存在、未软删；
   - `crm_payment_id IS NULL`，否则 400「CRM 来源充值请在 CRM 回款页撤销」。
3. 余额回退：`real -= record.real`、`bonus -= record.bonus`、`total = real + bonus`。
4. 余额不足（`real < record.real` 或 `bonus < record.bonus`）：
   - 非超管 → 403；
   - 超管且 `force=False` → 409；
   - `force=True` → 执行，允许负余额，返回 `needs_manual_reconciliation=true` + `shortfall_*`。
5. 软删记录：`record.deleted_at = cst_now()`（不改金额字段）。
6. 审计 `billing_recharge_revoke`：`changes` = 记录快照（金额、备注、凭证、操作人、归期）、
   `balance_before/after`、`reason`、`forced`、`needs_manual_reconciliation`、`shortfall_*`。

## 统计口径修复（同批，否则余额与统计矛盾）

| 文件 | 修改 |
|---|---|
| `services/invoice_excel.py` | 结算单期间充值汇总加 `RechargeRecord.deleted_at.is_(None)` |
| `services/analytics.py` | 充值趋势聚合、历史累计充值各加 `deleted_at` 过滤 |

余额列表/导出/本月充值/最近充值已过滤，无需改。

## 权限

- `scripts/seed.py`：`billing:recharge_revoke`（billing 组，描述「撤销充值记录」）。
- `tests/_test_data.py`：同步权限行。
- `scripts/fix_add_recharge_revoke_permission.py`：存量库幂等补权限 + 仅关联超级管理员 + 失效权限缓存。

## 前端

`views/billing/components/RechargeRecordModal.vue`（余额管理 → 记录 → 充值记录 tab）：

- 新增「操作」列：`crm_payment_id` 为空且有 `billing:recharge_revoke` → 「撤销」；
  CRM 来源显示 `CRM回款 #external_id`，无撤销按钮。
- 撤销弹窗：客户、实充/赠送、来源、归期、入账时间、撤销后余额预览、原因（必填）、
  超管「余额不足时强制撤销（线下核对欠款）」。
- 成功后刷新记录列表；父页面（`Balance.vue`）需在撤销后刷新余额列表。

## 风险与回滚

- 软删记录可通过清空 `deleted_at` 恢复，但余额需人工同步修正；审计是唯一资金留痕依据。
- 迁移：无（沿用现有 `deleted_at` 列）。
- 回滚：下线前端入口即可，后端接口无副作用；已撤销数据由审计追溯。
