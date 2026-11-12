# Audit Log Description Contract

> 审计日志「变更详情」的可读化契约：存储层结构 → 中文摘要 + 字段对照表。

---

## 1. 单一事实源

| 层 | 文件 | 职责 |
|---|---|---|
| 描述器 | `backend/app/services/audit_describe.py` | 把 `changes` / `extra_metadata` 渲染成 `action_label` / `module_label` / `summary[]` / `fields[]` |
| 列表路由 | `backend/app/routes/audit_logs.py` | 每行额外返回 `description`（原始 `changes` 不变） |
| 前端 | `frontend/src/views/system/AuditLogs.vue` | 列表列展示中文标签；详情弹窗展示摘要 + 字段表 + 折叠原始 JSON |

契约是**只读解释**：绝不改写 `audit_logs` 存储内容，金额/快照/敏感字段原值仍保留在 `changes` 中。

## 2. 响应字段

```jsonc
{
  "changes": { /* 原始存储结构，供追责复核 */ },
  "description": {
    "action_label": "撤销充值记录",
    "module_label": "结算",
    "record_type_label": "充值记录",
    "summary": ["撤销充值记录 #4669（客户 #27124）", "实充 ¥1,000.00，赠送 ¥0.00，归期 2026-11-12", "..."],
    "fields": [{ "label": "余额（实充）", "before": "¥243,800.00", "after": "¥242,800.00" }]
  }
}
```

- `fields` 只包含**真正变化**的行（`_values_equal` 过滤），无变化就是空数组。
- 未知字段回退为原始键名，不丢信息；`password*` / `token` / `secret` 一律渲染 `已脱敏`。
- 时间键（`*_at`、`*_date`）截断到秒展示（`YYYY-MM-DD HH:MM:SS`）。
- 金额键（`*_amount`/`*_price`/`*_fee`/`*_cost`/`*_spend` 及 `AMOUNT_KEYS`）渲染 `¥1,234.00`，负数为 `-¥1,234.00`。
- `status` 用结算单/ VR 合并的中文状态表；其它枚举走 `ENUM_LABELS`。

## 3. changes 结构兼容矩阵

| 结构 | 来源 | 处理 |
|---|---|---|
| `before` / `after` 对比 | 通用 CRUD、余额充值 | diff 字段 + 状态句 + 余额合计句 |
| 扁平业务快照（`reason`/`real_amount`/`balance_before`/`record_snapshot`…） | `recharge-revoke`、`crm-recharge-revoke` | 专用叙述句，不落成「无关字段」噪声 |
| `extra_metadata` 计数（`success_count`/`skipped_count`…） | 批量动作 | `成功 N 条；跳过 M 条` |
| `role_id` / `role_ids` 列表 | 权限分配 | `角色：20, 27` |
| 空 / 缺失 | 历史数据 | `取消（无详细变更数据）`，界面仍可打开 |

## 4. 写审计时必须遵守的两条（历史 bug 根因）

1. **变更前快照要先固化**
   ```python
   balance_before = await balance_service.get_balance_by_customer_id(customer_id)
   before_snapshot = {
       "real_amount": float(balance_before.real_amount or 0),
       "bonus_amount": float(balance_before.bonus_amount or 0),
   }
   ```
   同一 `AsyncSession` 的 identity map 会在 `recharge()` 后改写该 ORM 实例；
   晚读取 `balance_before.real_amount` 得到的是新值 → `before == after`（已修复于 `routes/billing/balances.py`）。

2. **一个动作只写一条业务审计**
   `middleware/audit.py` 会按 `method + path` 自动记录；凡路由内已写业务审计（含前后快照）的端点必须加入跳过规则：
   - `/api/v1/billing/recharge`（精确路径）
   - `/api/v1/billing/recharge-records/*/revoke`
   - `/api/v1/crm-recharge/payments/*/import` 与 `.../import/revoke`

   否则会多出 `action=create`、`changes={after: 请求体}` 的噪声行，与业务行重复。

## 5. 测试锚点

- `backend/tests/unit/test_audit_describe.py`：各 `changes` 结构 → 摘要/字段表/脱敏/时区格式。
- `backend/tests/integration/test_audit_recharge_snapshot.py`：真实充值 → 只有一条审计、`before`/`after` 为真实前后余额、`description.summary` 含金额与余额合计。
