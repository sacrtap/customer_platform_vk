# 余额充值记录撤销

余额管理「充值记录」支持逐条撤销手动/Excel 充值：软删记录 + 扣回余额。
CRM 来源充值（`crm_payment_id` 非空）必须走 CRM 回款页撤销（见
[crm-recharge-revoke](./crm-recharge-revoke.md)），余额页直接拒绝。

## 接口

```
POST /api/v1/billing/recharge-records/<record_id>/revoke
权限: billing:recharge_revoke + billing:view
body: {"reason": "<必填，≤500>", "force": false}
```

## 语义要点

1. **余额池化**：`recharge_records` 与 `consumption_records` 之间没有关联列，无法判断
   某笔充值是否已被消耗，只能以「当前余额是否够扣」为准。
2. **软删而非物理删除**：手动充值 `crm_payment_id IS NULL`，不受覆盖软删的唯一键约束，
   因此撤销写 `deleted_at` 保留金额/备注/凭证；资金留痕由审计 `billing_recharge_revoke`
   的 `record_snapshot` + `balance_before/after` 承担。
3. **锁序**：客户 → 余额行 → 充值记录（与 `BalanceService.recharge` 一致）。
   记录需先无锁读取以取得 `customer_id`；加锁后必须复核 `deleted_at`，保证并发重复
   请求只有一笔成功。
4. **余额不足**（资金已被消耗，`real/bonus` 不足以回退）：
   - 非超管 → `403`
   - 超管未传 `force` → `409`
   - 超管 `force=true` → 执行，余额可为负（欠款语义），返回
     `needs_manual_reconciliation=true` + `shortfall_real/bonus`
5. **软删时间写入**：`deleted_at` 是 naive 列，必须写 CST 墙钟
   （`cst_now().replace(tzinfo=None)`），直接写 aware datetime 会被 asyncpg 拒绝。

## 统计口径（软删必须被所有聚合遵守）

撤销后充值记录从以下口径消失，缺一处就会「余额已扣但统计仍算这笔钱」：

| 位置 | 说明 |
|---|---|
| `services/billing.py::get_recharge_records` | 记录列表 |
| `routes/billing/balances.py::apply_recharge_filters` | 余额列表/导出/本月充值/最近充值 |
| `services/invoice_excel.py` | 结算单期间充值汇总 |
| `services/analytics.py::get_balance_trend` | 月度充值聚合 + 趋势窗口前历史累计 |

新增任何 `RechargeRecord` 聚合都必须带 `RechargeRecord.deleted_at.is_(None)`。

## 测试锚点

- `tests/unit/test_recharge_revoke.py`：CRM 来源拒绝、已撤销拒绝、可见性、余额不足
  403/409、force 标记、审计快照。
- `tests/integration/test_billing_api.py::test_recharge_revoke_*`：软删后列表消失、
  余额回退、审计落库；`test_revoke_removes_recharge_from_balance_trend` 锁定趋势口径
  （撤销前该月余额 10000 → 撤销后 0）。
