# Design System Master File

> **LOGIC**: When building a specific page, first check `docs/design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Customer Platform VK
**Generated:** 2026-04-08 00:00:00
**Category:** B2B Service

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F172A` | `--color-primary` |
| Secondary | `#334155` | `--color-secondary` |
| CTA/Accent | `#0369A1` | `--color-cta` |
| Background | `#F8FAFC` | `--color-background` |
| Text | `#020617` | `--color-text` |

**Color Notes:** Professional navy + blue CTA

### Typography

- **Heading Font:** Plus Jakarta Sans
- **Body Font:** Plus Jakarta Sans
- **Mood:** friendly, modern, saas, clean, approachable, professional
- **Google Fonts:** [Plus Jakarta Sans + Plus Jakarta Sans](https://fonts.google.com/share?selection.family=Plus+Jakarta+Sans:wght@300;400;500;600;700)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #0369A1;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #0F172A;
  border: 2px solid #0F172A;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #0F172A;
  outline: none;
  box-shadow: 0 0 0 3px #0F172A20;
}
```

### Tables (表格)

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

#### 表格基础样式

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
```

#### 操作按钮样式

```css
/* 操作列 */
.table-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 文字按钮 */
.table-actions .btn-text {
  font-size: 14px; /* 统一为14px */
  font-weight: 500;
  padding: 6px 12px;
  color: #0369A1;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 150ms ease;
}

.table-actions .btn-text:hover {
  background: #E8F3FF;
}

/* 危险按钮 */
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

/* 分页信息 */
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

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Trust & Authority

**Keywords:** Certificates/badges displayed, expert credentials, case studies with metrics, before/after comparisons, industry recognition, security badges

**Best For:** Healthcare/medical landing pages, financial services, enterprise software, premium/luxury products, legal services

**Key Effects:** Badge hover effects, metric pulse animations, certificate carousel, smooth stat reveal

### Page Pattern

**Pattern Name:** Enterprise Gateway

- **Conversion Strategy:**  logo carousel,  tab switching for industries, Path selection (I am a...). Mega menu navigation. Trust signals prominent.
- **CTA Placement:** Contact Sales (Primary) + Login (Secondary)
- **Section Order:** 1. Hero (Video/Mission), 2. Solutions by Industry, 3. Solutions by Role, 4. Client Logos, 5. Contact Sales

---

## Anti-Patterns (Do NOT Use)

- ❌ Playful design
- ❌ Hidden credentials
- ❌ AI purple/pink gradients

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
