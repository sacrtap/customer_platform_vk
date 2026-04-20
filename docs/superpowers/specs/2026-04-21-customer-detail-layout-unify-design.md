# 客户详情页排版统一设计

**日期**: 2026-04-21
**状态**: 待实现

## 问题描述

客户详情页的 5 个 Tab 中，基础信息/画像信息/余额信息已有白色圆角卡片容器包装，但**结算单**和**用量数据**的表格区域缺少容器包装，视觉风格不一致。

## 目标

统一所有 Tab 内容的容器风格，使结算单和用量数据区域与其他 Tab 保持一致的卡片质感。

## 设计方案

### 1. 结算单 Tab
- 在 `<a-table>` 外层包裹 `<div class="data-table-card">`
- 样式：`background: white; border-radius: 12px; border: 1px solid var(--neutral-2); box-shadow: var(--shadow-sm); padding: 16px;`

### 2. 用量数据 Tab
- 保留现有 `usage-distribution-section`（已有卡片样式）
- 将 `usage-table-section` 升级为卡片容器（复用 `.data-table-card` 样式）
- 调整间距：`margin-top: 24px` 保持不变

### 3. CSS 复用
- 新增 `.data-table-card` 类，复用现有 CSS 变量（`--neutral-2`, `--shadow-sm`, `--radius-md`）
- 与 `tabs-section` 内的整体风格保持一致

## 影响范围
- `frontend/src/views/customers/Detail.vue`：模板 + 样式
