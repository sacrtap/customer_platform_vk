# 客户运营中台 - UI 设计规范文档

> **版本**: 1.1  
> **创建日期**: 2026-04-06  
> **最后更新**: 2026-04-08  
> **适用项目**: Customer Platform VK

---

## 📋 目录

1. [设计原则](#设计原则)
2. [色彩系统](#色彩系统)
3. [字体系统](#字体系统)
4. [布局与间距](#布局与间距)
5. [阴影与层次](#阴影与层次)
6. [组件规范](#组件规范)
7. [交互与动效](#交互与动效)
8. [响应式设计](#响应式设计)
9. [可访问性](#可访问性)
10. [设计资源](#设计资源)

---

## 设计原则

### 核心理念

| 原则 | 说明 |
|------|------|
| **专业可信** | 企业级 SaaS 产品，传递权威感和信任感 |
| **清晰高效** | 信息层级清晰，操作路径简短，提升工作效率 |
| **一致规范** | 统一的视觉语言和交互模式，降低学习成本 |
| **适度精致** | 避免过度设计，在功能性和美观性之间取得平衡 |

### 设计风格

**风格定位**: Trust & Authority（信任与权威）

- 使用稳重的深色系作为主色调
- 清晰的视觉层次和对比度
- 克制的动画效果，以功能性为主
- 避免娱乐化、过度活泼的设计元素

### 禁止使用的设计模式 ❌

- 表情符号作为图标
- 紫色/粉色 AI 渐变
- 布局抖动的悬停效果
- 低对比度文字
- 无过渡的瞬时状态变化
- 不可见的焦点状态

---

## 色彩系统

### 主色调

| 角色 | 色值 | CSS 变量 | 使用场景 |
|------|------|----------|----------|
| Primary (主色) | `#0F172A` | `--color-primary` | 侧边栏背景、重要文字、深色区域 |
| Secondary (辅助色) | `#334155` | `--color-secondary` | 次要文字、边框、分隔线 |
| CTA (强调色) | `#0369A1` | `--color-cta` | 主要按钮、链接、高亮状态 |

### 功能色

| 角色 | 色值 | CSS 变量 | 使用场景 |
|------|------|----------|----------|
| Success (成功) | `#22c55e` | `--color-success` | 成功状态、正向数据、完成标识 |
| Warning (警告) | `#f59e0b` | `--color-warning` | 警告提示、待处理状态 |
| Danger (危险) | `#ef4444` | `--color-danger` | 错误状态、删除操作、紧急提醒 |
| Info (信息) | `#3296f7` | `--color-info` | 信息提示、一般状态 |

### 中性色

| 色值 | CSS 变量 | 使用场景 |
|------|----------|----------|
| `#F8FAFC` | `--neutral-1` | 页面背景、卡片背景 |
| `#E8F3FF` | `--neutral-2` | 浅色背景、悬停状态 |
| `#E0E2E7` | `--neutral-3` | 边框、分隔线 |
| `#C9CDD4` | `--neutral-4` | 禁用状态、占位符 |
| `#8F959E` | `--neutral-5` | 次要文字、图标 |
| `#646A73` | `--neutral-6` | 说明文字 |
| `#4C5360` | `--neutral-7` | 常规文字 |
| `#1D2330` | `--neutral-10` | 标题文字、重要内容 |

### 色彩使用示例

```css
/* 主按钮 */
.btn-primary {
  background: linear-gradient(135deg, #3296f7 0%, #0369A1 100%);
  color: white;
}

/* 成功状态徽章 */
.status-badge.success {
  background: #e8ffea;
  color: #22c55e;
}

/* 警告状态徽章 */
.status-badge.warning {
  background: #fff7e8;
  color: #f59e0b;
}
```

---

## 字体系统

### 字体家族

```css
font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```

**Google Fonts 引入**:
```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
```

### 字体大小与字重

| 用途 | 大小 | 字重 | 行高 | 示例 |
|------|------|------|------|------|
| 大标题 | 28px | 700 | 1.2 | 页面标题 |
| 主标题 | 24px | 700 | 1.2 | 卡片标题 |
| 次标题 | 20px | 700 | 1.3 | 模块标题 |
| 正文大 | 16px | 400/500 | 1.5 | 表单输入 |
| 正文 | 14px | 400/500 | 1.5 | 常规内容 |
| 辅助文字 | 13px | 400 | 1.5 | 说明文字 |
| 小字 | 12px | 400/500 | 1.4 | 标签、徽章 |
| 微小字 | 11px | 600 | 1.3 | 角标、优先级 |

### 文字颜色规范

| 文字类型 | 色值 | 对比度 |
|----------|------|--------|
| 标题文字 | `#1D2330` | ≥ 7:1 |
| 正文文字 | `#4C5360` | ≥ 4.5:1 |
| 次要文字 | `#8F959E` | ≥ 3:1 |
| 禁用文字 | `#C9CDD4` | - |
| 链接文字 | `#0369A1` | ≥ 4.5:1 |

---

## 布局与间距

### 间距系统

| Token | 值 | 使用场景 |
|-------|-----|----------|
| `--space-xs` | `4px` / `0.25rem` | 图标与文字间隙、紧凑排列 |
| `--space-sm` | `8px` / `0.5rem` | 表单项间隙、按钮内边距 |
| `--space-md` | `16px` / `1rem` | 标准内边距、卡片内边距 |
| `--space-lg` | `24px` / `1.5rem` | 模块间距、大卡片内边距 |
| `--space-xl` | `32px` / `2rem` | 页面内边距、大模块间距 |
| `--space-2xl` | `48px` / `3rem` | 页面边距、分区间距 |
| `--space-3xl` | `64px` / `4rem` | 英雄区内边距 |

### 布局容器

```css
/* 侧边栏 */
.sidebar {
  width: 260px;           /* 展开状态 */
  width: 64px;            /* 收起状态 */
}

/* 顶部栏 */
.header {
  height: 64px;
}

/* 内容区 */
.page-content {
  padding: 32px;
}

/* 卡片 */
.card {
  padding: 24px;
  border-radius: 16px;
}
```

### 栅格系统

```css
/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);  /* 桌面端 */
  gap: 24px;
}

/* 仪表盘网格 */
.dashboard-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;  /* 桌面端 */
  gap: 24px;
}
```

---

## 阴影与层次

### 阴影层级

| 层级 | 值 | 使用场景 |
|------|-----|----------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.04)` | 轻微悬浮、输入框焦点 |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.08)` | 卡片、按钮 |
| `--shadow-lg` | `0 12px 32px rgba(0,0,0,0.12)` | 下拉菜单、弹窗 |
| `--shadow-xl` | `0 24px 64px rgba(0,0,0,0.16)` | 登录框、大弹窗 |

### 使用示例

```css
/* 统计卡片 */
.stat-card {
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--neutral-2);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

/* 登录框 */
.login-container {
  box-shadow: var(--shadow-xl);
}

/* 按钮 */
.btn-primary {
  box-shadow: 0 2px 8px rgba(3, 105, 161, 0.2);
}

.btn-primary:hover {
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}
```

---

## 组件规范

### 按钮

#### 主要按钮
```css
.btn-primary {
  height: 48px;
  padding: 12px 32px;
  background: linear-gradient(135deg, #3296f7 0%, #0369A1 100%);
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}

.btn-primary:hover {
  background: linear-gradient(135deg, #0369A1 0%, #035a8a 100%);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.4);
  transform: translateY(-1px);
}
```

#### 次要按钮
```css
.btn-default {
  height: 48px;
  padding: 12px 24px;
  background: white;
  border: 1.5px solid #E0E2E7;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 500;
  color: #4C5360;
  cursor: pointer;
  transition: all 200ms ease;
}

.btn-default:hover {
  border-color: #3296f7;
  color: #0369A1;
  background: #E8F3FF;
}
```

#### 文字按钮
```css
.btn-text {
  padding: 6px 12px;
  background: transparent;
  color: #0369A1;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
}

.btn-text:hover {
  background: #E8F3FF;
  color: #035a8a;
}
```

### 输入框

```css
.form-input {
  width: 100%;
  height: 48px;
  padding: 12px 16px 12px 48px;  /* 左侧预留图标位置 */
  border: 1.5px solid #E0E2E7;
  border-radius: 12px;
  font-size: 15px;
  color: #1D2330;
  transition: all 200ms ease;
  outline: none;
}

.form-input::placeholder {
  color: #8F959E;
}

.form-input:hover {
  border-color: #60b1fa;
}

.form-input:focus {
  border-color: #0369A1;
  box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.1);
}
```

### 卡片

```css
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

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #1D2330;
}

.card-body {
  padding: 24px;
}
```

### 状态徽章

```css
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
```

### 表格

#### 表格字体大小规范（重要）

为确保表格视觉一致性，所有表格元素必须遵循以下字号规范：

| 元素 | 字号 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| 表头 (th) | **14px** | 600 | 1.5 | 列标题 |
| 表格内容 (td) | **14px** | 400 | 1.5 | 数据单元格 |
| 操作按钮 | **14px** | 500 | 1.5 | 编辑、删除等操作 |
| 状态徽章 | **12px** | 500 | 1.4 | 状态标签 |
| 分页文字 | **14px** | 400 | 1.5 | 分页器文字 |

**⚠️ 禁止使用的字号**：10px、11px、13px（会造成视觉不一致）

**✅ 实施检查清单：**
- [ ] 表格基础字号设置为 14px (`font-size: 14px`)
- [ ] 表头字重 600，内容字重 400
- [ ] 所有操作按钮字号统一为 14px
- [ ] 状态徽章可适当缩小至 12px
- [ ] 分页组件文字统一为 14px
- [ ] 禁止出现 10px、11px、13px 等不一致字号

#### 表格样式代码

```css
/* 表格容器 */
.table-container {
  overflow-x: auto;
  background: white;
  border-radius: 12px;
  border: 1px solid #E8F3FF;
}

/* 基础表格 */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px; /* 统一基础字号 */
}

/* 表头样式 */
th {
  text-align: left;
  padding: 14px 16px;
  font-size: 14px; /* 统一为14px */
  font-weight: 600;
  color: #4C5360;
  background: #F8FAFC;
  border-bottom: 1px solid #E8F3FF;
  white-space: nowrap;
}

/* 表体单元格 */
td {
  padding: 14px 16px;
  font-size: 14px; /* 统一为14px */
  font-weight: 400;
  color: #4C5360;
  border-bottom: 1px solid #E8F3FF;
  vertical-align: middle;
}

/* 最后一行无边框 */
tr:last-child td {
  border-bottom: none;
}

/* 行悬停效果 */
tr:hover td {
  background: #F8FAFC;
}

/* 操作列按钮 */
.table-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.table-actions .btn-text {
  font-size: 14px; /* 统一为14px */
  font-weight: 500;
  padding: 6px 12px;
  color: #0369A1;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 150ms ease;
}

.table-actions .btn-text:hover {
  background: #E8F3FF;
  color: #035a8a;
}

.table-actions .btn-text-danger {
  color: #ef4444;
}

.table-actions .btn-text-danger:hover {
  background: #ffe8e8;
  color: #dc2626;
}
```

#### 分页组件样式

```css
/* 分页容器 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px;
  font-size: 14px; /* 统一为14px */
  color: #4C5360;
}

/* 分页文字 */
.pagination-info {
  font-size: 14px;
  color: #646A73;
  margin-right: 16px;
}

/* 分页按钮 */
.pagination .btn-page {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  font-size: 14px; /* 统一为14px */
  font-weight: 500;
  color: #4C5360;
  background: white;
  border: 1px solid #E0E2E7;
  border-radius: 6px;
  cursor: pointer;
  transition: all 150ms ease;
}

.pagination .btn-page:hover {
  border-color: #0369A1;
  color: #0369A1;
}

.pagination .btn-page.active {
  background: #0369A1;
  color: white;
  border-color: #0369A1;
}

.pagination .btn-page:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

### 侧边栏导航

```css
/* 导航项 */
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: all 150ms ease;
  cursor: pointer;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.nav-item.active {
  background: linear-gradient(135deg, #0369A1 0%, #035a8a 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}

/* 子菜单 */
.nav-submenu {
  margin-top: 4px;
  padding-left: 32px;
}

.nav-subitem {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
  transition: all 150ms ease;
}

.nav-subitem::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.nav-subitem:hover {
  background: rgba(255, 255, 255, 0.06);
  color: white;
}
```

---

## 交互与动效

### 过渡时间

| 类型 | 时长 | 缓动函数 | 使用场景 |
|------|------|----------|----------|
| 快速 | 150ms | `cubic-bezier(0.4, 0, 0.2, 1)` | 悬停状态、颜色变化 |
| 标准 | 200ms | `cubic-bezier(0.4, 0, 0.2, 1)` | 按钮、卡片交互 |
| 慢速 | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` | 侧边栏展开、大组件 |
| 展开 | 300ms | `ease-in-out` | 子菜单展开/收起 |

### 悬停效果

```css
/* 按钮悬停 */
.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(3, 105, 161, 0.4);
}

/* 卡片悬停 */
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 导航项悬停 */
.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

/* 待办事项悬停 */
.todo-item:hover {
  background: white;
  border-color: #E0E2E7;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transform: translateX(4px);
}
```

### 焦点状态

```css
/* 输入框焦点 */
.form-input:focus {
  border-color: #0369A1;
  box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.1);
}

/* 按钮焦点 */
.btn:focus-visible {
  outline: 2px solid #0369A1;
  outline-offset: 2px;
}

/* 导航项焦点 */
.nav-item:focus-visible {
  outline: 2px solid rgba(50, 150, 247, 0.5);
  outline-offset: -2px;
}
```

### 加载状态

```css
/* 按钮加载 */
.btn.loading {
  pointer-events: none;
  opacity: 0.7;
}

.btn.loading::after {
  content: '';
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

---

## 响应式设计

### 断点定义

| 断点 | 宽度 | 适用设备 |
|------|------|----------|
| Mobile | 375px | 小屏手机 |
| Mobile Large | 414px | 大屏手机 |
| Tablet | 768px | 平板 |
| Desktop | 1024px | 小屏电脑 |
| Desktop Large | 1440px | 大屏电脑 |

### 响应式布局

```css
/* 统计卡片 - 桌面端 4 列 */
.stats-grid {
  grid-template-columns: repeat(4, 1fr);
}

/* 平板端 2 列 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

/* 移动端 1 列 */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .sidebar {
    transform: translateX(-100%);
  }
  
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  
  .main-content {
    margin-left: 0;
  }
}
```

### 移动端适配要点

- [ ] 最小触摸目标 44x44px
- [ ] 正文最小字号 16px
- [ ] 无横向滚动
- [ ] 侧边栏使用抽屉式
- [ ] 内容区域适当增加内边距

---

## 可访问性

### 色彩对比度

所有文字必须满足 WCAG 2.1 AA 标准：

| 文字类型 | 最小对比度 |
|----------|-----------|
| 正常文字 (<18px) | 4.5:1 |
| 大文字 (≥18px) | 3:1 |
| 图标 | 3:1 |

### 键盘导航

```css
/* 确保焦点可见 */
*:focus-visible {
  outline: 2px solid #0369A1;
  outline-offset: 2px;
}

/* 跳过链接 */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: #0369A1;
  color: white;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

### 屏幕阅读器支持

```html
<!-- 图标添加 aria-hidden -->
<svg aria-hidden="true">...</svg>

<!-- 按钮添加 aria-label -->
<button aria-label="搜索">
  <svg>...</svg>
</button>

<!-- 状态变化使用 role -->
<div role="status" aria-live="polite">加载中...</div>
```

### 动画偏好

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 设计资源

### 图标库

推荐使用 **Heroicons** 或 **Lucide Icons**:

- Heroicons: https://heroicons.com
- Lucide: https://lucide.dev

**使用规范**:
- 所有图标使用 SVG 格式
- 统一使用 24x24 viewBox
- 线条图标 stroke-width=2
- 保持图标风格一致

### 原型文件

| 页面 | 文件路径 |
|------|----------|
| 登录页 | `docs/prototypes/login.html` |
| 仪表盘 | `docs/prototypes/dashboard.html` |

### 设计工具

- **Figma**: UI 设计与协作
- **Coolors**: 配色方案生成
- **WebAIM**: 色彩对比度检查

### 参考链接

- [WCAG 2.1 指南](https://www.w3.org/WAI/WCAG21/quickref/)
- [Google Fonts](https://fonts.google.com)
- [Arco Design Vue](https://arco.design/vue)

---

## 附录：交付前检查清单

### 视觉质量

- [ ] 未使用表情符号作为图标
- [ ] 所有图标来自统一的图标集
- [ ] 悬停状态不引起布局抖动
- [ ] 直接使用主题色，不使用 var() 包装

### 交互体验

- [ ] 所有可点击元素有 `cursor: pointer`
- [ ] 悬停状态提供清晰的视觉反馈
- [ ] 过渡动画流畅 (150-300ms)
- [ ] 焦点状态对键盘导航可见

### 表格样式检查（重要）

- [ ] 表头 (th) 字号为 **14px**，字重 600
- [ ] 表格内容 (td) 字号为 **14px**，字重 400
- [ ] 操作按钮字号为 **14px**，字重 500
- [ ] 状态徽章字号为 **12px**，字重 500
- [ ] 分页文字字号为 **14px**，字重 400
- [ ] **未使用** 10px、11px、13px 等不一致字号
- [ ] 所有表格元素垂直居中对齐 (`vertical-align: middle`)
- [ ] 表格行悬停时有明显的背景色变化

### 对比度与可访问性

- [ ] 浅色模式文字对比度 ≥ 4.5:1
- [ ] 玻璃/透明元素在浅色模式下可见
- [ ] 边框在两种模式下都可见
- [ ] 所有图片有 alt 文本
- [ ] 表单输入有 label
- [ ] 颜色不是唯一的指示器
- [ ] 尊重 `prefers-reduced-motion`

### 布局与响应式

- [ ] 悬浮元素与边缘有适当间距
- [ ] 内容不被固定导航栏遮挡
- [ ] 在 375px、768px、1024px、1440px 测试响应式
- [ ] 移动端无横向滚动

---

**文档结束**
