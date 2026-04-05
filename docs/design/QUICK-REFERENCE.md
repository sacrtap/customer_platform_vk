# 设计快速参考卡片

> 客户运营中台 - 开发速查手册  
> 更新日期：2026-04-06

---

## 🎨 色彩速查

### 主色
```
Primary:    #0F172A  █  深蓝/侧边栏
CTA:        #0369A1  █  强调色/按钮
Secondary:  #334155  █  辅助色
Background: #F8FAFC  █  页面背景
```

### 功能色
```
Success: #22c55e  █  成功
Warning: #f59e0b  █  警告
Danger:  #ef4444  █  错误
Info:    #3296f7  █  信息
```

---

## 📐 间距速查

```
--space-xs:   4px   (0.25rem)  图标间隙
--space-sm:   8px   (0.5rem)   表单项
--space-md:  16px   (1rem)     标准内边距
--space-lg:  24px   (1.5rem)   模块间距
--space-xl:  32px   (2rem)     页面内边距
```

---

## 🔤 字体速查

```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
```

| 用途 | 大小 | 字重 |
|------|------|------|
| 标题 | 24-28px | 700 |
| 正文 | 14-16px | 400/500 |
| 辅助 | 12-13px | 400 |

---

## 🎭 阴影速查

```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.04)     轻微悬浮
--shadow-md: 0 4px 12px rgba(0,0,0,0.08)    卡片/按钮
--shadow-lg: 0 12px 32px rgba(0,0,0,0.12)   下拉/弹窗
--shadow-xl: 0 24px 64px rgba(0,0,0,0.16)   登录框
```

---

## 🔘 按钮样式

### 主要按钮
```css
.btn-primary {
  height: 48px;
  background: linear-gradient(135deg, #3296f7, #0369A1);
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(3, 105, 161, 0.3);
}
```

### 次要按钮
```css
.btn-default {
  height: 48px;
  background: white;
  border: 1.5px solid #E0E2E7;
  border-radius: 12px;
}
```

### 文字按钮
```css
.btn-text {
  padding: 6px 12px;
  background: transparent;
  color: #0369A1;
}
```

---

## 📦 组件速查

### 输入框
```css
.form-input {
  height: 48px;
  border: 1.5px solid #E0E2E7;
  border-radius: 12px;
  font-size: 15px;
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
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
```

### 状态徽章
```css
.status-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
}

.status-badge.success { background: #e8ffea; color: #22c55e; }
.status-badge.warning { background: #fff7e8; color: #f59e0b; }
.status-badge.danger  { background: #ffe8e8; color: #ef4444; }
.status-badge.info    { background: #e8f3ff; color: #0369A1; }
```

---

## ⚡ 动效参数

```css
/* 过渡时间 */
--transition-fast:  150ms  悬停/颜色
--transition-base:  200ms  按钮/卡片
--transition-slow:  250ms  侧边栏/大组件

/* 缓动函数 */
cubic-bezier(0.4, 0, 0.2, 1)
```

### 悬停效果
```css
:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.1);
  transition: all 200ms ease;
}
```

---

## 📱 响应式断点

```css
/* Mobile first */
@media (min-width: 768px)  { /* Tablet */ }
@media (min-width: 1024px) { /* Desktop */ }
@media (min-width: 1440px) { /* Large Desktop */ }

/* Max width */
@media (max-width: 1200px) { /* 统计卡片 2 列 */ }
@media (max-width: 768px)  { /* 移动端布局 */ }
```

---

## ✅ 交付检查清单

### 必须满足
- [ ] 无 emoji 图标 → 使用 SVG
- [ ] 所有可点击元素 `cursor: pointer`
- [ ] 悬停过渡 150-300ms
- [ ] 文字对比度 ≥ 4.5:1
- [ ] 焦点状态可见
- [ ] 响应式测试：375px, 768px, 1024px, 1440px

### 禁止使用
- ❌ 表情符号作为图标
- ❌ 紫色/粉色 AI 渐变
- ❌ 布局抖动的悬停
- ❌ 低对比度文字
- ❌ 无过渡的瞬时变化

---

## 🔗 资源链接

- **完整规范**: `docs/design/DESIGN-SPEC.md`
- **原型文件**: `docs/prototypes/`
- **图标库**: https://heroicons.com | https://lucide.dev
- **字体**: https://fonts.google.com/specimen/Plus+Jakarta+Sans

---

**快速参考结束**
