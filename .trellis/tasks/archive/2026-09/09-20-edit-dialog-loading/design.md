# 编辑弹窗 loading 居中修复 — Design

## 目标

`frontend/src/views/customers/detail/EditCustomerDialog.vue` 打开编辑弹窗加载数据期间，
loading 图标在弹窗可视区域（modal body 600px 高）内垂直水平居中。

## Root Cause（PRD 已确认，代码核实一致）

模板为 `<a-spin :loading="fetchLoading">` 包裹表单，内容 div 用 `v-show="!fetchLoading"` 隐藏。
加载态时 a-spin 无显式高度 → 容器（`.arco-spin`）高度塌陷，
`.arco-spin-loading` 覆盖层内图标无法在 600px 弹窗内垂直居中。

## 方案

给 a-spin 根节点添加专属 class（如 `edit-dialog-spin`），在 `<style scoped>` 中：

1. 加载态时容器保持弹窗 body 同等高度（`min-height: 600px`，与 `:body-style` 高度一致）；
2. 覆盖层 `.arco-spin-loading` 使用 flex 垂直水平居中（`display: flex; align-items: center; justify-content: center;`）；
3. loading 结束（表单显示）后无额外高度/布局影响——只作用于 loading 态，避免布局抖动。

实现时用 `:deep()` 命中 `.arco-spin` / `.arco-spin-loading`，不侵入 a-modal 其他部分。

```vue
<!-- 模板 -->
<a-spin :loading="fetchLoading" class="edit-dialog-spin">
  <div v-show="!fetchLoading"><!-- 表单 --></div>
</a-spin>
```

```css
/* 样式 */
.edit-dialog-spin :deep(.arco-spin) {
  min-height: 600px; /* 与 :body-style 600px 对齐，防止塌陷 */
}
.edit-dialog-spin :deep(.arco-spin-loading) {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

## 验收

- [ ] 打开编辑弹窗、数据加载期间，loading 图标在弹窗内居中
- [ ] 加载完成后表单布局与加载前一致，无布局抖动
- [ ] 响应式宽度（modalWidth 720px / 90vw / 95vw）下均居中
- [ ] 前端 `vue-tsc` type-check 通过；浏览器实测确认
