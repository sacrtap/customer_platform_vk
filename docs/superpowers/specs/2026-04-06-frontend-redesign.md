# 前端重构设计规范

**日期**: 2026-04-06  
**范围**: 所有前端页面基于已确认的设计规范和原型进行重构  
**技术栈**: Vue 3.4 + TypeScript + Arco Design 2.54

---

## 🎨 设计规范来源

1. **主设计规范**: `docs/design/DESIGN-SPEC.md`
2. **快速参考**: `docs/design/QUICK-REFERENCE.md`
3. **设计系统**: `docs/design-system/customer-platform-vk/MASTER.md`
4. **原型参考**: 
   - `docs/prototypes/login.html`
   - `docs/prototypes/dashboard.html`

---

## 📋 核心设计参数

### 色彩系统
```ts
// 主色
const PRIMARY = {
  DEFAULT: '#0F172A',    // 深海军蓝
  CTA: '#0369A1',        // 天空蓝 (按钮/链接)
  5: '#3296f7',          // 渐变亮色
  7: '#035a8a',          // 渐变暗色
}

// 功能色
const SUCCESS = '#22c55e'
const WARNING = '#f59e0b'
const DANGER = '#ef4444'
const INFO = '#3296f7'

// 中性色
const NEUTRAL = {
  1: '#F8FAFC',   // 背景
  2: '#E8F3FF',   // 浅色背景
  3: '#E0E2E7',   // 边框
  5: '#8F959E',   // 次要文字
  7: '#4C5360',   // 常规文字
  10: '#1D2330',  // 标题文字
}
```

### 字体系统
```ts
// 已在 main.ts 引入
font-family: 'Plus Jakarta Sans', sans-serif

// 字号规范
const FONT = {
  xs: '11px',    // 角标
  sm: '12px',    // 标签/徽章
  md: '14px',    // 正文
  lg: '16px',    // 表单输入
  xl: '20px',    // 次标题
  '2xl': '24px', // 主标题
  '3xl': '28px', // 大标题
}
```

### 间距系统
```ts
const SPACE = {
  xs: '4px',   // 图标间隙
  sm: '8px',   // 表单项
  md: '16px',  // 标准内边距
  lg: '24px',  // 模块间距
  xl: '32px',  // 页面内边距
}
```

### 圆角规范
```ts
const RADIUS = {
  sm: '8px',   // 小按钮/徽章
  md: '10px',  // 导航项
  lg: '12px',  // 输入框/卡片
  xl: '16px',  // 大卡片
  '2xl': '24px', // 登录框
}
```

---

## 📄 页面重构清单

### 1. 登录页面 (Login.vue)
**参考原型**: `docs/prototypes/login.html`

**重构要点**:
- [ ] 双栏布局 (左侧品牌展示 + 右侧登录表单)
- [ ] 渐变背景 + 浮动光球动画
- [ ] 品牌 Logo + 系统名称
- [ ] 核心功能卖点展示 (3 项)
- [ ] 系统统计数据展示
- [ ] 表单输入框带图标前缀
- [ ] 记住我复选框 (自定义样式)
- [ ] 忘记密码链接
- [ ] 登录按钮 (渐变背景 + 阴影)
- [ ] 响应式 (移动端隐藏品牌栏)

**颜色**:
- 背景：`linear-gradient(135deg, #0F172A 0%, #1e293b 50%, #0f172a 100%)`
- 主按钮：`linear-gradient(135deg, #3296f7 0%, #0369A1 100%)`

---

### 2. 仪表盘布局 (Dashboard.vue)
**参考原型**: `docs/prototypes/dashboard.html`

**重构要点**:
- [ ] 侧边栏导航 (可折叠/展开)
- [ ] 顶部栏 (搜索/通知/设置/退出)
- [ ] 用户信息显示区
- [ ] 面包屑导航
- [ ] 页面标题区

**侧边栏规范**:
- 宽度：展开 260px / 收起 64px
- 背景：`linear-gradient(180deg, #1D2330 0%, #2f3645 100%)`
- 导航项高度：48px
- 导航项圆角：10px
- 当前选中：渐变背景 + 阴影

**顶部栏规范**:
- 高度：64px
- 背景：white
- 边框：`1px solid #E8F3FF`
- 操作按钮：40x40px

---

### 3. 首页 (Home.vue)
**参考原型**: `docs/prototypes/dashboard.html` (统计卡片区域)

**重构要点**:
- [ ] 4 个统计卡片网格
- [ ] 卡片顶部彩色指示条
- [ ] 统计数值 + 变化趋势
- [ ] 月度回款趋势图表 (ECharts)
- [ ] 待办事项列表
- [ ] 最近结算单表格

**统计卡片规范**:
- 背景：white
- 圆角：16px
- 边框：`1px solid #E8F3FF`
- 阴影：`0 1px 2px rgba(0,0,0,0.04)`
- 悬停效果：上移 2px + 阴影加深

---

### 4. 客户管理页面 (customers/Index.vue, Detail.vue)
**重构要点**:
- [ ] 多条件筛选表单
- [ ] 标签组合筛选 (高级筛选)
- [ ] 表格展示 + 服务端分页
- [ ] 操作列 (查看/编辑/画像/结算单/余额/删除)
- [ ] 批量导入/导出按钮
- [ ] 状态徽章 (客户等级)

---

### 5. 用户管理页面 (users/Index.vue)
**重构要点**:
- [ ] 用户列表表格
- [ ] 角色分配
- [ ] 启用/禁用状态
- [ ] 创建/编辑用户弹窗

---

### 6. 角色管理页面 (roles/Index.vue)
**重构要点**:
- [ ] 角色列表
- [ ] 权限配置树形选择器
- [ ] 系统角色标识
- [ ] 创建/编辑角色弹窗

---

### 7. 标签管理页面 (tags/Index.vue)
**重构要点**:
- [ ] 标签分类展示 (客户标签/画像标签)
- [ ] 标签创建/编辑
- [ ] 标签使用数量统计
- [ ] 标签删除确认

---

### 8. 结算管理页面 (billing/Balance.vue, PricingRules.vue)
**重构要点**:
- [ ] 余额管理表格
- [ ] 充值记录
- [ ] 计费规则配置表单
- [ ] 结算单生成向导
- [ ] 结算单详情页面

---

### 9. 系统管理页面 (system/SyncLogs.vue, AuditLogs.vue)
**重构要点**:
- [ ] 日志列表表格
- [ ] 时间范围筛选
- [ ] 日志详情弹窗
- [ ] 导出功能

---

## 🔧 组件规范

### 按钮组件
```vue
<template>
  <a-button 
    :type="type" 
    :size="size"
    :loading="loading"
    :disabled="disabled"
    class="custom-btn"
  >
    <slot />
  </a-button>
</template>

<script setup lang="ts">
defineProps<{
  type?: 'primary' | 'default' | 'text'
  size?: 'small' | 'default' | 'large'
  loading?: boolean
  disabled?: boolean
}>()
</script>

<style scoped>
.custom-btn {
  border-radius: 12px;
  font-weight: 600;
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.custom-btn[type="primary"] {
  background: linear-gradient(135deg, #3296f7 0%, #0369A1 100%);
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}

.custom-btn[type="primary"]:hover {
  background: linear-gradient(135deg, #0369A1 0%, #035a8a 100%);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.4);
  transform: translateY(-1px);
}
</style>
```

### 状态徽章组件
```vue
<template>
  <span :class="['status-badge', status]">
    <span class="status-dot" />
    <slot />
  </span>
</template>

<script setup lang="ts">
defineProps<{
  status: 'success' | 'warning' | 'danger' | 'info'
}>()
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.success {
  background: #e8ffea;
  color: #22c55e;
}

.status-badge.warning {
  background: #fff7e8;
  color: #f59e0b;
}

.status-badge.danger {
  background: #ffe8e8;
  color: #ef4444;
}

.status-badge.info {
  background: #e8f3ff;
  color: #0369A1;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
</style>
```

### 卡片组件
```vue
<template>
  <div class="card">
    <div v-if="$slots.header" class="card-header">
      <slot name="header" />
    </div>
    <div class="card-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.card {
  background: white;
  border-radius: 16px;
  border: 1px solid #E8F3FF;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  transition: all 200ms ease;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #E8F3FF;
}

.card-body {
  padding: 24px;
}
</style>
```

---

## 📱 响应式断点

```ts
const BREAKPOINTS = {
  mobile: '375px',
  mobileLarge: '414px',
  tablet: '768px',
  desktop: '1024px',
  desktopLarge: '1440px',
}

// CSS 媒体查询
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
```

---

## ✅ 交付标准

### 视觉质量
- [ ] 无 emoji 图标，使用 SVG (Heroicons/Lucide)
- [ ] 所有图标来自统一图标集
- [ ] 悬停状态不引起布局抖动
- [ ] 直接使用主题色

### 交互体验
- [ ] 所有可点击元素有 `cursor: pointer`
- [ ] 悬停状态提供清晰视觉反馈
- [ ] 过渡动画流畅 (150-300ms)
- [ ] 焦点状态对键盘导航可见

### 可访问性
- [ ] 文字对比度 ≥ 4.5:1
- [ ] 表单输入有 label
- [ ] 颜色不是唯一指示器
- [ ] 尊重 `prefers-reduced-motion`

### 代码质量
- [ ] TypeScript 类型完整
- [ ] ESLint 无警告
- [ ] Prettier 格式化
- [ ] 组件有注释说明

---

## 🧪 测试要求

### E2E 测试 (Playwright)
- [ ] 登录流程
- [ ] 页面渲染验证
- [ ] 核心功能流程

### 代码质量
- [ ] ESLint + Prettier 检查
- [ ] TypeScript 类型检查
- [ ] 生产构建测试

---

## 📦 实施顺序

1. **Phase 1**: 登录页面 → 仪表盘布局 → 首页
2. **Phase 2**: 客户管理 → 用户管理 → 角色管理
3. **Phase 3**: 标签管理 → 结算管理 → 系统管理
4. **Phase 4**: 测试验证 → 代码质量检查 → 构建验证

---

**备注**: 每个页面重构完成后，需要运行测试验证并通过 ESLint/Prettier 检查才能标记为完成。
