# 编辑页消费等级显示金额范围

## Goal

客户管理编辑页中选择消费等级时，参考规模等级的选项显示方案，显示对应等级的金额范围。

## Background（已确认事实，来源：代码探索）

- 编辑页 `frontend/src/views/customers/detail/EditCustomerDialog.vue:128-136` 消费等级选项硬编码 `<a-option value="C1">C1</a-option>`，无金额信息
- 同文件规模等级选项（61-70 行）采用 `S（超大型 5000人）` 格式：等级 + 括号说明
- 消费等级档位口径（`backend/app/models/customers.py:101`）：C1/C2/C3/C4/C5/C6 = 100万/50万/25万/12万/6万/6万以下
- 共享常量 `CONSUME_LEVEL_OPTIONS`（`frontend/src/constants/customerOptions.ts:63`）为 `C1 - 100万` 单值格式，被筛选器/批量编辑引用，**本任务不改动该常量**（避免影响其他页面）

## Requirements

- R1 编辑页消费等级下拉每个选项显示「等级 + 金额范围区间」，参考规模等级括号说明样式

## Acceptance Criteria

- [ ] AC1 编辑页消费等级下拉选项为：
  - C1（100万以上）
  - C2（50万-100万）
  - C3（25万-50万）
  - C4（12万-25万）
  - C5（6万-12万）
  - C6（6万以下）
- [ ] AC2 选值与提交数据不变（仍为 C1~C6），仅选项展示文案变化
- [ ] AC3 编辑页其余字段无变化

## Out of Scope

- 修改 `CONSUME_LEVEL_OPTIONS` 共享常量（影响筛选器/批量编辑/分析页）
- 修改消费等级取值字典

## Key Decisions

- 区间表述由用户确认：C1（100万以上）、C2（50万-100万）、C3（25万-50万）、C4（12万-25万）、C5（6万-12万）、C6（6万以下）
