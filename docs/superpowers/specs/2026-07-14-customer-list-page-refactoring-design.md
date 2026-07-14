# 客户列表页面重构设计

## 概述

**目标**：将 `http://localhost:5173/customers` 页面按 `prototype/customers.html` 设计进行重构对齐，包括页面 Header、筛选、表格、批量操作、弹窗、抽屉等全部区域。

**原则**：
- 保持 Vue 3 + Arco Design 技术栈不变
- 不修改前端架构选型
- 考虑组件复用性，提取共享 UI 组件
- 新建专用组件：差异过大时新建确保 1:1 对齐

**数据来源**: `prototype/customers.html` + `prototype/css/style.css` + `prototype/js/customers.js`

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                customers/Index.vue (页面组装)             │
├─────────────────────────────────────────────────────────┤
│  业务组件层                                               │
│  ┌────────────┐ �────────────� ┌──────────────────┐    │
│  │CustomerKpi │ │CustomerFilter│ │CustomerTable    │    │
│  └────────────� └────────────┘ └──────────────────�    │
│  ┌────────────┐ �────────────� ┌──────────────────┐    │
│  │BatchToolbar│ │PreviewDrawer│ │ CustomerModals   │    │
│  └────────────� └────────────┘ └──────────────────�    │
├─────────────────────────────────────────────────────────┤
│  共享 UI 组件层                                           │
│  ┌──────┐ ┌──────────�Card│ │ProgressBar│ │      │  │
│  │Tag   │ │FilterDrop│ │KpiCard│ │ProgressBar│ │      │  │
│  └──────┘ └──────────┘ └───────�─�      │  │
│  �──────� ┌──────────┐ ┌───────┐ ┌──────────────────┐  │
│  │Drawer│ │ModalLayout│ │Section│ │ColumnSettingPanel│  │
│  └──────┘ └──────────� └───────┘ └──────────────────�  │
└─────────────────────────────────────────────────────────┘
```

### 实施顺序

| Phase | 输出物 | 描述 |
|-------|--------|------|
| Phase 1 | `components/ui/*.vue` | 8 个共享 UI 组件 |
| Phase 2 | `views/customers/components/*.vue` | 业务组件重构 |
| Phase 3 | `views/customers/Index.vue` | 页面组装 + 样式对齐 |
| Phase 4 |后端序列化调整 | 新增字段返回 |

---

## 共享 UI 组件设计

### Tag 标签组件

```
路径: src/components/ui/Tag.vue
Props:
  - variant: 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'gray' (默认 gray)
  - size: 'sm' | 'md' (默认 md)
Slots: 默认 — 标签文字
```

样式规范（来源 prototype/css/style.css）:
- 圆角 999px, padding 4px 8px, 字体 12px bold
- 语义色映射：blue=#DBEAFE/#1D4ED8, green=#DCFCE7/#047857, amber=#FEF3C7/#B45309, red=#FEE2E2/#B91C1C, violet=#EDE9FE/#6D28D9, gray=#F1F5F9/#475569

### FilterDropdown 筛选下拉组件

```
路径: src/components/ui/FilterDropdown.vue
Props:
  - label: string (筛选字段名称)
  - modelValue: string | string[] (当前选中值)
  - options: Array<{label: string, value: string}>
  - multiple: boolean (是否多选)
Events:
  - update:modelValue
  - apply (多选确认后触发)
```

交互规范：
- 点击触发按钮展开下拉面板
- 单选：选择后自动收起并触发 apply
- 多选：勾选后点击确认按钮触发 apply
- 面板样式: absolute 定位，白色背景，轻阴影

### KpiCard 指标卡片

```
路径: src/components/ui/KpiCard.vue
Props:
  - label: string
  - value: string | number
  - trend?: string
  - trendType?: 'up' | 'down' | 'warn' | 'neutral'
  - active?: boolean (选中态高亮)
Events: click
```

### ProgressBar 进度条

```
路径: src/components/ui/ProgressBar.vue
Props:
  - value: number (0-100)
  - color?: string (默认 var(--primary))
```

### Drawer 抽屉

```
路径: src/components/ui/AppDrawer.vue (或复用 Arco Drawer)
Props:
  - visible: boolean
  - title: string
  - width?: string (默认 420px)
  - closable?: boolean (默认 true)
Slots: 默认 + footer
Events: update:visible, close
```

### ModalLayout 通用弹窗

```
路径: src/components/ui/ModalLayout.vue
Props:
  - visible: boolean
  - title: string
  - size: 'sm' | 'md' | 'lg' | 'xl'
  - maskClosable?: boolean (默认 false)
Slots: 默认 + footer + header-extra
Events: update:visible, confirm, cancel
```

### CheckboxArray 复选框组

```
路径: src/components/ui/CheckboxArray.vue
Props:
  - modelValue: string[]
  - options: Array<{label: string, value: string}>
  - columns?: number (默认 4 列网格)
Events: update:modelValue
```

---

## 业务组件设计

### CustomerKpi 客户指标卡片组

```
路径: src/views/customers/components/CustomerKpi.vue
组合: KpiCard × 4 横向 grid-4 布局
Props: 各指标数值 + 趋势数据
Events: kpi-change(kpiType)
```

KPI 类型: `all` | `key` | `incomplete` | `mine`

### CustomerFilters 筛选器

```
路径: src/views/customers/components/CustomerFilters.vue (重构)
组合: 搜索框 + FilterDropdown × 6 + 筛选按钮
Props/Events: 保持现有 filters v-model + search/reset 事件
```

注意: 保留 a-collapse 实现的高级筛选入口，但默认视图使用 FilterDropdown 一行布局

### CustomerTable 客户表格

```
路径: src/views/customers/components/CustomerTable.vue (重构)
基于: Arco Design a-table (暂不自绘表格)
列定义:
  - name (客户名+Logo+重点标记) — 220px
  - industry (行业+标签) — 150px
  - scale_level (规模等级) — 100px
  - consume_level (消费等级) — 100px
  - balance (余额) — 120px sortable
  - usage_30d (30天消耗进度条) — 140px sortable
  - health (健康度Tag) — 100px
  - settlement_type — 110px
  - manager_id — 100px
  - sales_manager_id — 100px
  - account_type — 100px
  - created_at — 160px
  - action (操作) — 200px fixed:right
列设置: 右上角齿轮图标，CheckboxArray 勾选显隐，保存到 localStorage
```

交互: 行点击 → PreviewDrawer；Checkbox → BatchToolbar；列排序

### PreviewDrawer 客户预览抽屉

```
路径: src/views/customers/components/PreviewDrawer.vue (重建)
结构:
  ├── 头部: Logo+名称+行业/等级摘要
  ├── KPI 4宫格: 当前余额/30天消耗/健康度/预计耗尽
  ├── 最近操作时间线 (可选，后端数据暂缺时跳过)
  └── 底部操作区: 查看详情/生成结算单/提醒充值
Props:
  - visible: boolean
  - customerId: number
注意 数据暂缺 KPI 时仅展示基础信息区
```

### BatchToolbar 批量工具栏

```
路径: src/views/customers/components/BatchToolbar.vue (扩展)
Props: count: number
按钮: 批量编辑 | 分配负责人 | 批量导出 | 设标签
样式: 背景 #EFF6FF，横贯表格顶部，左侧数量提示
```

### CustomerModals 弹窗集合

```
路径: src/views/customers/components/CustomerModals.vue (容器)
包含9个弹窗:
  1. CustomerFormModal — 新增/编辑客户
  2. ImportModal — 导入客户
  3. ExportModal — 导出（范围+格式+字段）
  4. BatchEditModal — 批量编辑字段
  5. AssignManagerModal — 批量分配运营/销售经理
  6. BatchExportModal — 批量导出（范围+格式+字段）
  7. BatchTagModal — 设标签（添加/移除+标签多选）
  8. ColumnSettingModal — 列设置（CheckboxArray）
触发: 父组件 ref 管理 visible 状态
```

---

## 数据字段映射

### API 序列化调整（最小改动）

当前 list API 返回字段:
- id, company_id, name, account_type, industry, industry_type_id
- price_policy, manager_id, sales_manager_id, settlement_cycle
- settlement_type, is_key_customer, is_real_estate, email, created_at

**新增返回字段** (Part A — 已有模型字段):

| 字段 | 来源 | 序列化方式 |
|------|------|-----------|
| `scale_level` | `customer.profile.scale_level` | JOIN + 提取 |
| `consume_level` | `customer.profile.consume_level` | JOIN + 提取 |
| `balance` | `customer.balance.total_amount` | 已加载关系 |

**暂不实现** (Part B — 后续迭代):

| 字段 | 原因 | 表格显示 |
|------|------|---------|
| `usage_30d` | 需聚合 DailyConsumption 计算 | 显示 `-` 或进度条 0% |
| `health` | 需计算逻辑（余额+消耗速率） | 显示灰色 Tag `-` |

---

## 样式对齐规范

### CSS 设计令牌

```css
:root {
  --bg: #F6F8FB;
  --panel: #FFFFFF;
  --ink: #0F172A;
  --muted: #475569;
  --line: #DBE3EF;
  --primary: #1D4ED8;
  --primary-hover: #2563EB;
  --cyan: #0891B2;
  --green: #059669;
  --amber: #D97706;
  --red: #DC2626;
  --violet: #7C3AED;
  --shadow: 0 14px 40px rgba(15,23,42,.08), 0 2px 6px rgba(15,23,42,.04);
  --radius: 18px;
  --radius-sm: 12px;
}
```

### 字体规范

| 用途 | 字号 | 字重 |
|------|------|------|
| 页面标题 h1 | 26px | 850 |
| 卡片标题 | 17px | 700 |
| 表头 | 12px | 600 |
| 正文 | 14px | 400 |
| 辅助文字 | 12px | 400 muted |

### 间距规范

- 页面内边距: 24px
- 卡片间距: 14px
- 区块间距: 18px
- 组件内间距: 12px / 16px

### 按钮样式

- `btn-primary`: 渐变蓝底 + 白色文字 + 投影
- `btn-secondary/default`: 灰底/边框 + 深色文字
- hover: 主按钮上浮 1px + 阴影增强；次按钮背景加深

---

## 关键交互流程

### 1. 页面初始化

```
Index.vue mounted
  → useCustomerList composable 加载数据
  → useCustomerList 提供: customers, pagination, filters, kpi data
  → 表格渲染 + KPI 卡片渲染
```

### 2. 筛选流程

```
用户操作 FilterDropdown 选择筛选值
  → emit update:modelValue
  → emit apply / search
  → composable 处理过滤参数
  → API 请求刷新列表
```

### 3. 行点击 → 预览抽屉

```
用户点击表格行 (非 Checkbox/操作按钮)
  → emit view(customerId)
  → Index.vue: previewDrawerVisible = true; previewCustomerId = id
  → PreviewDrawer 根据 customerId 加载摘要数据
```

### 4. 批量操作

```
用户勾选表格行 → BatchToolbar 出现
  → 点击按钮打开对应弹窗
  → 弹窗提交 → refresh 列表
```

### 5. 列设置

```
用户点击齿轮图标 → ColumnSettingModal
  → CheckboxArray 展示所有可配置列
  → 用户勾选/取消 → 保存到 localStorage
  → 表格根据配置动态显示/隐藏列
```

---

## 风险与注意事项

### 后端 API 改动风险
- **影响范围**: list API 序列化增加 JOIN 查询
- **缓解**: CustomerBalance 和 CustomerProfile 已在 `selectinload` 中加载，额外字段提取不会增加 SQL 查询

### 组件兼容性
- **Arco Design 模态框**: 弹窗内部布局使用 form-grid 需确认与 a-form 兼容性
- **缓解**: ModalLayout 封装 Arco a-modal，内部使用原生 CSS grid

### localStorage 持久化
- 列设置存 localStorage key: `customer_table_columns_config`
- 版本升级时可清除旧配置

---

## 验收标准

1. **视觉对齐**: 页面整体观感与 prototype/customers.html 一致（背景、卡片、字体、间距、配色）
2. **功能完整**: 筛选、排序、分页、行选择、批量操作、弹窗、抽屉均可用
3. **组件复用**: UI 共享组件可独立使用，不依赖业务上下文
4. **数据展示**: 现有列正常显示，新增列有合理降级（后端暂缺字段显示占位）
5. **响应式**: 960px / 640px 断点下布局正常（折叠侧边栏、自适应）
