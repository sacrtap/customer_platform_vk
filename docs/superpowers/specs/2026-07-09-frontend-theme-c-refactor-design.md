# 前端 Theme-C 风格重构设计规格

**日期**：2026-07-09  
**状态**：待审核  
**版本**：1.0

---

## 1. 概述

### 1.1 背景

当前客户运营中台前端采用 Vue 3 + Arco Design Vue 技术栈，视觉风格与 theme-c 原型存在差异。为提升用户体验和视觉一致性，决定将全部 18 个页面迁移到 theme-c 风格。

### 1.2 目标

- 将所有页面视觉风格统一为 theme-c 原型设计
- 保持 Vue 3 技术栈，采用混合方案（Arco + Tailwind）
- 分三阶段完成重构，降低风险
- 简化部分复杂功能，提升易用性

### 1.3 范围

**包含**：
- 18 个路由页面的视觉重构
- 布局组件重写（侧边栏、顶栏）
- 基础 UI 组件开发（卡片、筛选栏等）
- Arco Design 主题定制

**不包含**：
- 后端 API 变更
- 业务逻辑重构
- 数据库结构调整

---

## 2. 技术决策

### 2.1 技术栈

```
Vue 3.4.15 + Arco Design Vue 2.54.3 + Tailwind CSS 3 + Pinia + vue-router
```

### 2.2 方案选择

**选择方案 C：混合方案**

| 方案 | 描述 | 优点 | 缺点 | 选择 |
|-----|------|------|------|------|
| A | 保留 Arco + CSS 覆盖 | 改动最小 | 灵活性有限 | ❌ |
| B | 替换为 Tailwind + Headless UI | 完全匹配风格 | 工作量巨大 | ❌ |
| C | 混合方案（Arco + Tailwind） | 平衡工作量和灵活性 | 需维护两套样式 | ✅ |

**选择理由**：
- 复杂组件（表格、表单）保留 Arco，避免功能丢失
- 布局、卡片、按钮等用 Tailwind，完全匹配 theme-c
- 工作量合理，可渐进式迁移

### 2.3 分支策略

**单分支完成所有阶段**：
- 分支名：`feature/theme-c-refactor`
- 三个阶段都在此分支完成
- 最后一次性合并到主分支

---

## 3. 架构设计

### 3.1 样式系统分层

```
┌─────────────────────────────────────────┐
│  全局主题层 (tailwind.config.js)          │
│  - 颜色系统：theme-c 色板                 │
│  - 字体：Inter + JetBrains Mono          │
│  - 间距/圆角/阴影                        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  组件样式层                              │
│  - Arco 组件：arco-theme.css 覆盖        │
│  - 自定义组件：Tailwind 工具类           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  页面样式层                              │
│  - 布局：Tailwind                        │
│  - 页面特定样式：scoped CSS              │
└─────────────────────────────────────────┘
```

### 3.2 组件职责划分

| 组件类型 | 实现方式 | 示例 |
|---------|---------|------|
| **布局组件** | Tailwind CSS | 侧边栏、顶栏、页面容器 |
| **基础 UI** | Tailwind CSS | 卡片、按钮、标签、徽章 |
| **复杂交互** | Arco Design | 表格、表单、日期选择、上传 |
| **图表** | ECharts | 保持现有实现 |

### 3.3 目录结构调整

```
frontend/src/
├── assets/
│   └── styles/
│       ├── tailwind.css          # Tailwind 入口
│       ├── arco-theme.css        # Arco 主题覆盖（更新）
│       └── variables.css         # CSS 变量（theme-c 色板）
├── components/
│   ├── layout/                   # 布局组件（Tailwind）
│   │   ├── AppSidebar.vue        # 重写
│   │   ├── AppHeader.vue         # 重写
│   │   └── PageContainer.vue     # 新增
│   ├── ui/                       # 基础 UI 组件（Tailwind）
│   │   ├── StatCard.vue          # 新增
│   │   ├── DataTable.vue         # 封装 Arco Table
│   │   └── FilterBar.vue         # 新增
│   └── charts/                   # 保持现有
└── views/                        # 页面组件
```

---

## 4. 组件设计规范

### 4.1 布局组件

#### AppSidebar.vue

**视觉特征**：
- 背景色：`#1E1B4B`（深靛蓝）
- 宽度：`224px`（w-56）
- 导航项：水平布局（图标 + 文字）
- 激活状态：左侧 3px 圆角指示条 + 半透明靛蓝背景
- 悬停状态：白色半透明背景

**关键样式**：
```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.nav-item.active {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 3px;
  background: #6366F1;
  border-radius: 0 2px 2px 0;
}

.nav-item:not(.active):hover {
  background: rgba(255, 255, 255, 0.08);
}
```

#### AppHeader.vue

**视觉特征**：
- 背景色：白色
- 底部边框：`border-b border-gray-200`
- 面包屑：灰色文字 + 当前页黑色
- 用户头像：圆形 + 下拉菜单

### 4.2 基础 UI 组件

#### StatCard.vue（统计卡片）

**视觉特征**：
- 背景：白色
- 边框：`border border-gray-200`
- 圆角：`rounded-lg`
- 内边距：`p-4`
- 标题：`text-xs font-medium text-gray-500 uppercase`
- 数值：`text-2xl font-semibold text-gray-900`
- 变化趋势：绿色/红色 + 图标

#### FilterBar.vue（筛选栏）

**视觉特征**：
- 背景：白色
- 边框：`border border-gray-200`
- 圆角：`rounded-lg`
- 内边距：`p-4`
- 搜索框：左侧图标 + 圆角边框
- 高级筛选：折叠面板

**功能简化**：
- 多条件筛选改为：搜索框 + 高级筛选折叠
- 默认显示常用筛选条件
- 高级筛选展开后显示完整条件

### 4.3 复杂交互组件

#### DataTable.vue（封装 Arco Table）

**视觉特征**：
- 表头：`background: #F9FAFB; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase`
- 单元格：`padding: 12px 16px; border-bottom: 1px solid #F3F4F6`
- 悬停：`background: #F9FAFB`
- 字体大小：`13px`

**样式覆盖**：
```css
.data-table :deep(.arco-table-th) {
  background: #F9FAFB;
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #6B7280;
}

.data-table :deep(.arco-table-td) {
  padding: 12px 16px;
  border-bottom: 1px solid #F3F4F6;
}

.data-table :deep(.arco-table-tr:hover .arco-table-td) {
  background: #F9FAFB;
}
```

### 4.4 主题色板

**tailwind.config.js**：
```js
module.exports = {
  theme: {
    extend: {
      colors: {
        indigo: {
          50: '#EEF2FF',
          500: '#6366F1',
          600: '#4F46E5',
          900: '#312E81',
        },
        gray: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
        sidebar: {
          bg: '#1E1B4B',
          active: 'rgba(99,102,241,0.18)',
          hover: 'rgba(255,255,255,0.08)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'xs': ['12px', { lineHeight: '16px' }],
        'sm': ['13px', { lineHeight: '20px' }],
        'base': ['14px', { lineHeight: '20px' }],
        'lg': ['16px', { lineHeight: '24px' }],
        'xl': ['20px', { lineHeight: '28px' }],
        '2xl': ['24px', { lineHeight: '32px' }],
      },
    },
  },
}
```

---

## 5. 页面迁移策略

### 5.1 第一阶段：核心布局 + 关键页面

**目标**：建立基础设施，验证风格可行性

| 页面 | 迁移策略 | 工作量 |
|-----|---------|-------|
| **AppSidebar.vue** | 完全重写（Tailwind） | 中 |
| **AppHeader.vue** | 完全重写（Tailwind） | 小 |
| **Login.vue** | 完全重写（Tailwind） | 中 |
| **Home.vue**（仪表盘） | 重写布局 + 保留图表 | 大 |
| **customers/Index.vue** | 重写布局 + 封装 DataTable | 大 |

**交付物**：
- Tailwind 配置完成
- 布局组件可复用
- 3 个核心页面可用

### 5.2 第二阶段：结算管理模块

**目标**：完成业务核心模块

| 页面 | 迁移策略 | 工作量 |
|-----|---------|-------|
| **billing/Balance.vue** | 重写布局 + 保留表格 | 中 |
| **billing/PricingRules.vue** | 重写布局 + 保留表单 | 中 |
| **billing/BillingRecords.vue** | 重写布局 + 保留表格 | 中 |
| **customers/Detail.vue** | 重写布局 + 保留功能 | 大 |

**交付物**：
- 结算管理完整可用
- 客户详情页可用

### 5.3 第三阶段：其余页面

**目标**：完成所有页面迁移

| 页面 | 迁移策略 | 工作量 |
|-----|---------|-------|
| **tags/Index.vue** | 重写布局 | 小 |
| **users/Index.vue** | 重写布局 + 保留表格 | 中 |
| **roles/Index.vue** | 重写布局 + 保留权限配置 | 中 |
| **系统工具页面** | 重写布局 | 小 |
| **Profile.vue** | 重写布局 | 小 |

**交付物**：
- 所有页面迁移完成
- 统一视觉风格

### 5.4 迁移原则

1. **布局优先**：先迁移页面整体布局（容器、间距、卡片）
2. **功能保留**：复杂交互（表格筛选、批量操作）保留 Arco 实现
3. **渐进增强**：每阶段可独立交付，不阻塞其他工作
4. **样式隔离**：页面特定样式使用 scoped CSS，避免污染全局

---

## 6. 实施计划概览

### 6.1 阶段划分

**第一阶段**（预计 3-5 天）：
- 安装配置 Tailwind CSS
- 重写 AppSidebar、AppHeader
- 重构 Login、Home、customers/Index
- 创建基础 UI 组件（StatCard、FilterBar、DataTable）

**第二阶段**（预计 2-3 天）：
- 重构结算管理 4 个页面
- 重构客户详情页

**第三阶段**（预计 2-3 天）：
- 重构其余 9 个页面
- 整体测试和优化

### 6.2 风险控制

- **功能丢失**：复杂组件保留 Arco 实现，仅调整样式
- **样式冲突**：使用 scoped CSS 和命名空间隔离
- **性能问题**：Tailwind 按需生成，不影响打包体积
- **回滚方案**：单分支开发，可随时放弃

---

## 7. 验收标准

### 7.1 视觉验收

- [ ] 所有页面风格统一为 theme-c 原型
- [ ] 侧边栏深靛蓝背景 + 左侧圆角指示条
- [ ] 卡片极简风格（border + rounded）
- [ ] 表格紧凑（11px 表头，13px 内容）
- [ ] 字体：Inter + JetBrains Mono

### 7.2 功能验收

- [ ] 所有现有功能正常可用
- [ ] 表格筛选、批量操作等复杂功能保留
- [ ] 图表展示正常
- [ ] 权限控制正常

### 7.3 性能验收

- [ ] 页面加载时间无明显增加
- [ ] 打包体积控制在合理范围
- [ ] 无样式冲突和闪烁

---

## 8. 附录

### 8.1 参考资料

- theme-c 原型：`prototype/theme-c/`
- Tailwind CSS 文档：https://tailwindcss.com/docs
- Arco Design Vue 文档：https://arco.design/vue

### 8.2 相关文档

- 项目 README：`README.md`
- 开发规范：`.omp/AGENTS.md`
- 测试规范：`.omp/rules/testing.md`
