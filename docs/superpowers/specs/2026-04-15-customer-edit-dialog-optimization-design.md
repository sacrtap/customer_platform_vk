# 客户详情编辑弹框三列布局优化 - 设计文档

**日期**: 2026-04-15
**状态**: 待审批
**涉及文件**: `frontend/src/views/customers/Detail.vue`

---

## 1. 概述

将客户详情页的编辑弹框从当前单列垂直布局改为**分组三列布局**，优化字段排序和位置，并添加基础表单验证。

---

## 2. 当前状态

- 编辑弹框使用 `a-modal` 默认宽度（约 520px）
- 所有 21 个表单项以单列垂直排列
- 无表单验证规则
- 字段按添加顺序排列，缺乏逻辑分组

---

## 3. 目标布局

### 3.1 三列分组方案

| 第一列：基础信息 | 第二列：结算与业务 | 第三列：画像与状态 |
|-----------------|-------------------|-------------------|
| 客户名称（必填）| 结算方式（必填）    | 规模等级          |
| 公司 ID（必填） | 结算周期           | 消费等级          |
| 账号类型        | 合作状态           | 首次回款时间      |
| 行业类型        | 所属 ERP           | 接入时间          |
| 客户等级        | 运营经理           | 重点客户          |
| 邮箱            | 销售负责人         | 是否结算          |
|                 |                   | 是否停用          |

**跨列区域**：备注（全宽 textarea）

### 3.2 弹窗宽度

- 响应式宽度：
  - `>= 1400px`: `width: 1100px`
  - `< 1400px`: `width: 800px`（降级为两列）
  - `< 768px`: `width: 100%`（降级为单列）

---

## 4. 表单验证规则

### 4.1 必填项

| 字段     | 验证规则                          | 错误提示                |
| -------- | --------------------------------- | ----------------------- |
| 公司 ID  | 必填 + 服务端排重校验              | "公司 ID 不能为空"       |
| 客户名称 | 必填，最长 200 字符                | "客户名称不能为空"       |

### 4.2 格式校验

| 字段             | 验证规则                                      | 错误提示                           |
| ---------------- | --------------------------------------------- | ---------------------------------- |
| 邮箱             | 可选填，但填写后必须符合邮箱格式               | "邮箱格式不正确"                    |
| 首次回款时间     | 不能超过今天                                  | "首次回款时间不能超过今天"          |
| 接入时间         | 不能超过今天                                  | "接入时间不能超过今天"              |
| 首次回款时间 vs 接入时间 | 首次回款时间不能早于接入时间（两者都填写时） | "首次回款时间不能早于接入时间"      |

### 4.3 服务端排重

- 公司 ID 编辑后，提交时调用后端接口校验唯一性
- 如果公司已存在且不是当前客户，返回错误提示："该公司 ID 已被其他客户使用"

---

## 5. 技术实现

### 5.1 模板变更

- 将 `a-modal` 添加 `:width="modalWidth"` 响应式计算属性
- 在表单区域使用 `div.edit-form-grid` 容器，内部三个 `div.edit-form-column`
- 每个字段包裹在 `a-form-item` 中，使用 `:rules` 定义验证规则
- 备注区域使用 `a-form-item` 跨列显示

### 5.2 验证实现

- 使用 Arco Design `a-form` 的 `:rules` 属性进行客户端验证
- 公司 ID 排重校验在 `handleEditSubmit` 中进行，提交前先调用校验接口
- 日期校验使用自定义 validator 函数

### 5.3 样式变更

```css
.edit-form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0 20px;
}

.edit-form-column {
  display: flex;
  flex-direction: column;
}

.edit-form-column + .edit-form-column {
  border-left: 1px solid var(--neutral-2);
  padding-left: 20px;
}

.edit-form-note {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-2);
}
```

### 5.4 响应式降级

```css
@media (max-width: 1399px) {
  .edit-form-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .edit-form-column:nth-child(2n) {
    border-left: none;
    border-right: 1px solid var(--neutral-2);
    padding-left: 0;
    padding-right: 20px;
  }
}

@media (max-width: 767px) {
  .edit-form-grid {
    grid-template-columns: 1fr;
  }
  .edit-form-column {
    border-left: none !important;
    border-right: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
  }
}
```

---

## 6. 字段变更对比

### 6.1 原有字段排序（单列）

1. 客户名称 → 2. 邮箱 → 3. 账号类型 → 4. 行业类型 → 5. 客户等级 → 6. 规模等级 → 7. 消费等级 → 8. 结算方式 → 9. 结算周期 → 10. 重点客户 → 11. 运营经理 → 12. 所属 ERP → 13. 销售负责人 → 14. 合作状态 → 15. 首次回款时间 → 16. 接入时间 → 17. 是否结算 → 18. 是否停用 → 19. 备注

### 6.2 新增字段

- **公司 ID** — 新增为可编辑字段（当前为只读展示），必填

---

## 7. 验收标准

1. 编辑弹框打开后，字段按三列分组显示
2. 必填字段带红色星号标记
3. 提交时触发客户端验证，错误提示显示在对应字段下方
4. 公司 ID 提交时服务端排重校验生效
5. 屏幕宽度缩小时自动降级为两列/单列布局
6. 表单提交成功后，弹框关闭并刷新客户详情数据
