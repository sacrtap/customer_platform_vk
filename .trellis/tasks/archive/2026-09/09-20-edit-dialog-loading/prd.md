# 编辑弹窗 loading 居中修复

## Goal

客户管理页点击「编辑」弹出的编辑客户弹窗（`EditCustomerDialog.vue`）加载数据时，loading 图标未在弹窗内居中显示（偏上/偏左）。

## Requirements

- 加载态时 loading 图标在弹窗可视区域（modal body 600px 高）内垂直水平居中。
- 加载完成后表单正常显示，不影响现有布局。

## Root Cause（已确认）

模板为 `<a-spin :loading="fetchLoading">` 包裹表单，内容 div 用 `v-show="!fetchLoading"` 隐藏。loading 时 a-spin 无显式高度，容器塌陷导致图标定位不居中。

## Acceptance Criteria

- [ ] 打开编辑弹窗、数据加载期间，loading 图标在弹窗内居中显示。
- [ ] 加载完成后表单布局与加载前一致，无布局抖动。
- [ ] 响应式宽度（`modalWidth` 720px / 90vw / 95vw）下均居中。
