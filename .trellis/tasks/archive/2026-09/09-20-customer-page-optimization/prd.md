# 客户管理页面功能优化

## Goal

客户管理页面 6 项功能优化，拆分为 3 个独立可验证的子任务：

1. **筛选选项增强**（`09-20-customer-filter-options`）：新增「是否结算」「是否停用」筛选项；补上「是否重点客户」「是否房产客户」UI 下拉（后端已支持）。
2. **编辑弹窗 loading 居中**（`09-20-edit-dialog-loading`）：修复编辑客户弹窗加载时 loading 图标未在弹窗内居中显示的问题。
3. **健康度评估排除规则**（`09-20-health-score-exclusion`）：客户详情页健康度评分排除「不结算」「客户测试账号」「内部账号」客户。

## Requirements

- 筛选项与客户列表筛选链路（前端 `CustomerFilters.vue` / `useCustomerList.ts` ↔ 后端 `routes/customers.py` / `services/customers.py`）保持一致，支持组合筛选。
- 编辑弹窗（`EditCustomerDialog.vue`）加载数据期间 loading 图标应在弹窗可视区域内垂直居中。
- 健康度评分（`get_customer_health_score`）对排除对象返回「不参与评估」语义，前端详情页有对应展示。
- 所有改动遵循项目硬规则（数据库事务、`@auth_required`、测试覆盖率、Python 3.12、文件修改前读取）。

## Constraints

- 健康度排除规则仅作用于客户详情页评分（`get_customer_health_score`），**不改动**健康度分析页统计（`get_customer_health_stats`，独立逻辑）。
- 「内容账号」按用户确认 = 现有「内部账号」类型，不新增账号类型。
- 任务 1 与任务 4 按用户澄清：第 1 条为「是否结算」，第 4 条为「是否停用」（非重复）。

## Child Task Map

| 子任务 | 交付物 | 验收入口 |
|---|---|---|
| 09-20-customer-filter-options | 4 个筛选项前后端完整链路 | 页面筛选项下拉 + 列表过滤正确 |
| 09-20-edit-dialog-loading | 弹窗 loading 居中样式 | 打开编辑弹窗观察 loading 位置 |
| 09-20-health-score-exclusion | 健康度排除规则 + 前端展示 | 排除客户详情页显示「不参与评估」 |

## Acceptance Criteria

- [ ] 三个子任务全部完成、各自验收通过。
- [ ] 客户列表页：是否结算 / 是否重点客户 / 是否房产客户 / 是否停用 四个筛选项均可选并正确过滤（含组合筛选）。
- [ ] 编辑客户弹窗加载数据时，loading 图标在弹窗内居中显示。
- [ ] 不结算、客户测试账号、内部账号客户在详情页不显示健康度分数，展示「不参与评估」。
- [ ] 健康度分析页行为不受本次改动影响。
- [ ] 后端测试覆盖新增筛选参数与健康度排除逻辑；前端类型检查通过。
