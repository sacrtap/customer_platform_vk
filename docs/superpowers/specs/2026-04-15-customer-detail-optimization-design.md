# 客户详情页功能优化设计文档

**创建日期**: 2026-04-15  
**状态**: 待实现  
**涉及模块**: 客户详情页面 (前端)

---

## 需求概述

对客户详情页面进行 5 项功能优化：

1. 基础信息列表改为双列显示
2. 编辑对话框增加规模等级字段
3. 画像信息删除"房地产行业"字段
4. 编辑对话框增加消费等级字段
5. 画像信息中消费等级显示格式优化

---

## 设计详情

### 1. 基础信息列表双列显示

**当前实现**: 使用 `<table>` 标签，单列布局（label-cell + value-cell），共 18 行数据。

**修改方案**: 
- 将 `<table>` 结构改为使用 Arco Design 的 `<a-descriptions>` 组件
- 设置 `:column="2"` 属性实现双列布局
- 保持原有数据字段不变

**影响文件**: `frontend/src/views/customers/Detail.vue`

**改动范围**: 
- 模板部分：替换 `<table class="info-table">` 为 `<a-descriptions>`
- 样式部分：移除 `.info-table` 相关 CSS，改用 Arco 默认样式或微调

### 2. 编辑对话框增加规模等级

**当前实现**: 编辑表单中无规模等级字段。

**修改方案**:
- 在编辑表单中新增 `<a-form-item>` 字段 `scale_level`
- 使用 `<a-select>` 下拉选择器
- 预设选项：
  - `100人` (值: "100")
  - `500人` (值: "500")
  - `1000人` (值: "1000")
  - `2000人` (值: "2000")
  - `5000人` (值: "5000")

**数据存储**: 该字段属于 `CustomerProfile` 模型，但编辑入口在客户编辑对话框中。需要通过现有 API 同时更新 profile 数据。

**影响文件**: 
- `frontend/src/views/customers/Detail.vue` (编辑表单)
- 可能需要调整 `handleEditSubmit` 逻辑，确保同时更新 profile 数据

### 3. 删除"房地产行业"字段

**当前实现**: 画像信息 tab 中有 4 个核心指标卡片，其中第 4 个是"房地产行业"（is_real_estate）。

**修改方案**:
- 移除对应的 `<div class="metric-card">` 卡片
- 核心指标区从 4 个卡片变为 3 个卡片

**影响文件**: `frontend/src/views/customers/Detail.vue`

### 4. 编辑对话框增加消费等级

**当前实现**: 编辑表单中无消费等级字段。

**修改方案**:
- 在编辑表单中新增 `<a-form-item>` 字段 `consume_level`
- 使用 `<a-select>` 下拉选择器
- 预设选项：
  - `S` (值: "S", 对应: 100万)
  - `A` (值: "A", 对应: 50万)
  - `B` (值: "B", 对应: 25万)
  - `C` (值: "C", 对应: 12万)
  - `D` (值: "D", 对应: 6万)

**数据存储**: 同规模等级，属于 `CustomerProfile` 模型。

### 5. 画像信息消费等级显示格式

**当前实现**: `{{ profile.consume_level || '-' }}` 仅显示等级字母（如 "S"）。

**修改方案**:
- 创建计算属性或工具函数，将等级映射为 `等级 - 值` 格式
- 映射关系：
  - S → "S - 100万"
  - A → "A - 50万"
  - B → "B - 25万"
  - C → "C - 12万"
  - D → "D - 6万"
  - 其他/null → "-"

**实现方式**: 使用 Vue computed 属性 `consumeLevelDisplay`

**影响文件**: `frontend/src/views/customers/Detail.vue`

---

## 技术要点

### 后端 API 考虑

现有更新客户的 API (`updateCustomer`) 仅更新 `Customer` 表字段。规模等级和消费等级存储在 `CustomerProfile` 表中。

**确认结果**: 
- ✅ 后端有独立的 `PUT /customers/<id>/profile` 接口 (`updateProfile` API)
- ✅ 前端已有 `updateProfile` 函数 (位于 `frontend/src/api/customers.ts`)

**实现方案**: 
- 在 `handleEditSubmit` 中，使用 `Promise.all` 同时调用 `updateCustomer` 和 `updateProfile`
- 两个 API 调用并行执行，任一失败则整体回滚提示
- 成功后刷新页面数据并清除缓存

### 类型定义

当前 `CustomerProfile` 类型已包含 `scale_level` 和 `consume_level` 字段（`string | null`），无需修改类型定义。

---

## 影响文件清单

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `frontend/src/views/customers/Detail.vue` | 模板 + 逻辑 + 样式 | 基础信息双列布局、编辑框新增字段、删除房地产行业、消费等级显示格式化 |
| `frontend/src/types/index.ts` | 无 | 已包含所需字段，无需修改 |

---

## 测试要点

1. **基础信息双列显示**: 验证页面渲染正确，字段对齐，响应式正常
2. **规模等级编辑**: 验证下拉选项正确，保存后数据更新成功
3. **消费等级编辑**: 验证下拉选项正确，保存后数据更新成功
4. **房地产行业删除**: 验证画像信息页面不再显示该字段
5. **消费等级显示**: 验证画像信息中消费等级显示为 "S - 100万" 格式

---

## 风险与注意事项

1. **编辑提交逻辑**: 已确认需要并行调用 `updateCustomer` 和 `updateProfile` 两个 API
2. **样式兼容性**: 双列布局需验证在不同屏幕尺寸下的显示效果
3. **数据一致性**: 编辑提交后需确保页面数据刷新正确

---

## 冗余字段分析（已决策）

### price_policy 字段

| 层级         | 状态                             |
| ------------ | -------------------------------- |
| 数据库模型   | ✅ 存在 (`customers.price_policy`) |
| 后端 API     | ✅ 返回（列表和详情接口都有）    |
| 前端类型定义 | ✅ 存在 (`Customer.price_policy`)  |
| 前端详情页   | ❌ 未显示                        |
| 前端编辑表单 | ❌ 未提供编辑入口                |

**决策**: 本次优化暂不处理 `price_policy` 字段，保持现有功能优化范围不变。后续可单独评估定价策略功能需求。
