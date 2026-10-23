# 技术设计 — require_reconciliation

## 状态机基线

`draft → pending_ops → pending_sales → pending_customer → customer_confirmed → completed`，任意非 completed 可 `cancelled`。

## submit 分流契约（核心改动）

现状：`submit_invoice` 按经理配置被动跳过（有 manager→pending_ops；无 manager 有 sales→pending_sales；皆无→pending_customer）。

新逻辑：前置显式开关——

```python
customer = await self._get_customer(invoice.customer_id)
require_recon = customer is not None and customer.require_reconciliation is True
if require_recon:
    if customer and customer.manager_id:
        invoice.status = "pending_ops"
    elif customer and customer.sales_manager_id:
        invoice.status = "pending_sales"
    else:
        # 防御：开对账但经理被清空（保存时已拦截，不应发生）→ 降级
        invoice.status = "pending_customer"
else:
    # 不对账：跳过经理确认，直接待客户确认
    invoice.status = "pending_customer"
```

- NULL 视为否（`is True` 严格判断）。
- `confirm_ops`/`confirm_sales`/`generate_invoice`/`generate_invoices_batch` 不变。

## 校验契约（客户保存入口）

- `create_customer`：`require_reconciliation is True` 时 `manager_id`、`sales_manager_id` 均必填，构造前抛 `ValueError`（路由层已转 40003）。
- `update_customer`：可更新字段赋值后、commit 前，综合本次传入值与现有值判断（未传字段回落到 `customer.*`）；显式传 `None` 清空经理同样视为未指定。

## 数据迁移

- 新迁移：`add_column require_reconciliation`（Boolean, nullable, server_default false）+ `drop_column auto_initiate_settlement`。
- downgrade 反向。原始迁移 `a2b3c4d5e6f7` 不改（alembic 历史不篡改；fresh install 先建后删无害）。
- 历史行迁移后均为 False → 默认否，符合需求，无回填。

## 前端语义统一

label「是否对账」；选项 是(true)/否(false)，默认 false；`require_reconciliation === true` 时 `manager_id`/`sales_manager_id` computed 动态 `:rules` required。批量编辑开对账不在前端逐条校验经理，依赖后端 batch-update 逐条 `update_customer` 报错回显。

## 兼容性

- 批量开对账但部分客户无经理：batch 路由沿用部分成功/失败聚合，失败行返回错误信息。
- 导入：`require_reconciliation` 走 `convert_bool_field`，默认 False。
