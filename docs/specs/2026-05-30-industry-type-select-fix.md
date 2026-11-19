# 客户列表编辑弹框行业类型不回显修复

> 归档来源：`.omo/plans/fix-industry-type-select.md`（2026-11-19 蒸馏归档，原件已删除）
> 状态：已实施 —— `backend/app/routes/customers.py` 列表响应已含 `"industry_type_id": c.profile.industry_type_id if c.profile else None`
> 锚点说明：文中 `文件:行号` 为 2026-05-30 期快照，定位以符号名与路径为准

## Context

**现象**：客户管理页搜索结果列表内点"编辑"，编辑弹框中"行业类型"不显示选中值。

**根因**：列表 API（`GET /api/v1/customers`）只返回 `industry` 名称字符串，不返回 `industry_type_id`；前端 `Index.vue` 读 `record.profile?.industry_type_id` 恒为 `null`（列表响应没有 `profile` 嵌套对象，详情 API 才带）。

**用户选择**：后端补字段（前端零改动），不改现有 `industry` 字段，不引入破坏性变更。

## Approach

`routes/customers.py` 列表响应在 `industry` 字段后增加：

```python
"industry_type_id": (
    c.profile.industry_type_id if c.profile else None
),
```

前端沿用既有 `record.profile?.industry_type_id` 逻辑即可回显。

## Critical files & anchors

- `backend/app/routes/customers.py` — 列表响应 `industry_type_id`（详情 API 响应格式为取值逻辑参考）

## Verification

- `curl -s "http://localhost:8000/api/v1/customers?page=1&page_size=1"` → `data.list[0]` 含 `"industry_type_id": <number|null>`
- 前端编辑弹框行业类型正确显示选中值；列表展示与编辑提交无回归
- 提交：`fix(customers): add industry_type_id to list API response`

## Assumptions

- 前端 `Customer` 类型中 `industry_type_id` 无需显式补充（`profile?` 本就可选，TS 编译不受影响）。
