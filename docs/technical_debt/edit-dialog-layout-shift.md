# EditCustomerDialog 布局抖动与尺寸优化

## 问题概述

编辑客户弹框（`EditCustomerDialog.vue`）存在三类问题：

1. **布局抖动**：选择空值字段后，校验消息出现/消失导致页面跳动
2. **右侧大量留白**：弹框宽度 960px 远超内容实际需求
3. **高度不固定**：弹框高度随内容变化，列间高度不均衡

## 修复历程

### 第一轮：布局抖动修复（commit `6736222`）

| 优先级 | 问题 | 修复方案 |
|--------|------|----------|
| P0-1 | 校验消息出现/消失导致高度跳动 | `:deep(.arco-form-item-message) { min-height: 22px }` 预留空间 |
| P0-2 | `a-row/a-col` 列高度不齐 | 替换为 CSS Grid 三列布局 (`grid-template-columns: repeat(3, 1fr)`) |
| P1-3 | `validate-trigger` 过于频繁 | 从 `['blur', 'change']` 改为 `['blur']` |
| P1-4 | 每次打开弹框重复加载字典数据 | `managers`/`cooperationStatuses`/`erpSystems` 改为 props 传入 |
| P2-5 | `settlement_type` 缺少 `allow-clear` | 添加 `allow-clear` |
| P2-6 | `a-spin` loading 切换导致 DOM 闪烁 | 用 `v-show="!fetchLoading"` 替代 |

### 第二轮：宽度与高度优化（commits `abc236f` → `520b962`）

- **宽度**：960px → 800px → 720px（基于内容列宽计算）
- **高度**：`max-height: 70vh` → `max-height: 55vh` + `overflow-y: auto`
- **间距**：`margin-bottom` 从默认 24px 减至 18px
- **列分配**：7/8/5 → 调整为更均衡的分布

### 第三轮：固定高度 + 列重排（commit `0af37c3`）

**高度方案**：`max-height: 55vh` → `height: 680px`（固定值）

- 680px 在 1080p 屏幕（viewport 高度 1080px）下占比 63%，留出标题栏 + 底部按钮空间
- 在 1440p 屏幕（viewport 高度 1440px）下占比 47%，视觉更紧凑
- 内容区域固定高度后，弹框整体高度不再随内容变化

**三列重排为 7/7/6 均衡分布**：

| 列 | 分组 | 字段数 | 包含字段 |
|----|------|--------|----------|
| 列一 | 客户标识 | 7 | name, company_id, email, account_type, industry_type_id, is_real_estate, scale_level |
| 列二 | 结算配置 | 7 | settlement_type, settlement_cycle, price_policy, erp_system, cooperation_status, is_settlement_enabled, consume_level |
| 列三 | 人员与状态 | 6 | sales_manager_id, manager_id, is_key_customer, is_disabled, first_payment_date, onboarding_date |
| 横跨 | 备注 | 1 | notes（`grid-column: 1 / -1`） |

**调整逻辑**：
- `scale_level` 从列三移到列一（客户标识属性更合适）
- `consume_level` 从列三移到列二（与结算配置相关）
- `sales_manager_id` 和 `manager_id` 从列一/列二移到列三（人员相关字段聚合）
- `is_disabled` 从列二移到列三（状态相关）

## 最终 CSS 关键配置

```css
/* 固定高度 680px + 内部滚动 */
:deep(.arco-modal-body) {
  height: 680px;
  overflow-y: auto;
  padding-right: 8px; /* 滚动条空间 */
}

/* 紧凑 form-item 间距 */
:deep(.arco-form-item) {
  margin-bottom: 18px;
}

/* 三列 Grid 布局 */
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  align-items: start;
}
```

## 涉及文件

- `frontend/src/views/customers/detail/EditCustomerDialog.vue` — 主修改文件
- `frontend/src/views/customers/Detail.vue` — 传递字典 props
- `frontend/src/composables/useCustomerDetail.ts` — 加载 cooperationStatuses/erpSystems
- `.trellis/spec/frontend/component-guidelines.md` — 新增 R7-R9 模态弹框尺寸规范

## 经验总结

1. **模态弹框高度优先用固定值**：`vh` 单位在不同屏幕上差异大，固定 px 值更可控
2. **Grid 布局优于 Flex 列**：`align-items: start` 保证三列独立生长，不会互相撑高
3. **字段分组按业务语义**：客户标识 → 结算配置 → 人员与状态，比"基础/业务/等级"更直觉
4. **Pre-commit hook 注意事项**：`end-of-file-fixer` 会修改文件内容，提交前需确保 ESLint/Prettier 已通过
