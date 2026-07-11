# 客户运营中台 — 设计规范

> 本文档从 `prototype/index.html` 和 `prototype/login.html` 两套原型中提取，作为后续 Vue 3 + Arco Design 开发的一致性基准。

## 交付文件

- `prototype/index.html`：单文件交互式高保真原型（含登录页入口、仪表盘 / 客户管理 / 客户详情 / 消耗分析 / 结算管理 / 系统治理 / 设计总览等 18+ 页面）
- `prototype/login.html`：登录页原型（左右分栏：品牌展示区 + 登录表单）

---

## 1. 设计定位

**紧凑型企业数据驾驶舱**：面向内部运营、结算、分析人员，优先保证信息密度、数据可读性和任务处理效率。

### 设计原则

1. **核心指标先行**：首屏 4-6 个 KPI 卡片，快速回答"是否正常、哪里异常、下一步做什么"
2. **筛选与结果同屏**：顶部筛选条 + 指标条 + 图表/表格，减少跳转
3. **异常优先排序**：余额不足、同步失败、结算失败、临期回款等风险使用状态标签 + 行动按钮
4. **少装饰、强层级**：浅灰背景、白色卡片、蓝色主操作、语义色表达趋势和风险
5. **可追溯操作**：客户详情、结算、系统治理页面突出时间线、操作者、状态和下一步动作

---

## 2. 设计令牌（Design Tokens）

以下 CSS 变量在 `index.html` 和 `login.html` 中完全一致，开发时应映射为 Arco Design 主题变量或 CSS 自定义属性。

### 2.1 色彩

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--bg` | `#F6F8FB` | 页面背景，降低密集表格视觉噪声 |
| `--panel` | `#FFFFFF` | 卡片、面板、弹窗背景 |
| `--ink` | `#0F172A` | 主文本 |
| `--muted` | `#475569` | 辅助文本、说明文字 |
| `--soft` | `#E2E8F0` | 分割线、hover 背景、次要边框 |
| `--line` | `#DBE3EF` | 默认边框、表格线 |

| 令牌 | 色值 | 用途 |
|------|------|------|
| `--primary` | `#1D4ED8` | 主按钮、关键趋势线、当前导航、链接 |
| `--primary-2` | `#2563EB` | 主色渐变终点、hover 态 |
| `--cyan` | `#0891B2` | 次级图表、同步状态、信息标签 |
| `--green` | `#059669` | 成功、正增长、健康 |
| `--amber` | `#D97706` | 预警、待处理、临期 |
| `--red` | `#DC2626` | 危险、失败、异常、负增长 |
| `--violet` | `#7C3AED` | 画像标签、特殊分类 |

**成功/危险语义类**（开发时补充对应的语义类）：

| 类名 | 用途 |
|------|------|
| `.success` / `.up` | 正向指标（绿色 `#059669`） |
| `.danger` / `.down` | 负向/危险（红色 `#DC2626`） |
| `.warn` | 预警（琥珀色 `#D97706`） |

### 2.2 深色面板（侧边栏 / 品牌区）

| 属性 | 值 |
|------|-----|
| 背景 | `radial-gradient(circle at 20% 0%, rgba(37,99,235,.28), transparent 32%), linear-gradient(180deg, #111C33 0%, #0B1220 100%)` |
| 文字 | `#CBD5E1`（正文）、`#93A4B8`（辅助）、`#64748B`（版权信息）、`white`（品牌/标题） |
| 边框 | `1px solid rgba(148,163,184,.16)` |
| 导航组背景 | `rgba(15,23,42,.20)`，`border-radius: 16px` |
| 折叠按钮边框 | `1px solid rgba(147,197,253,.24)` |
| 折叠按钮背景 | `linear-gradient(135deg,#1d4ed8,#0891b2)` |
| 折叠按钮阴影 | `0 10px 26px rgba(15,23,42,.30)` |
| 折叠按钮 hover | `translateX(2px)` + `box-shadow: 0 12px 30px rgba(37,99,235,.38)` |
| 二级菜单左边框 | `1px solid rgba(148,163,184,.22)` |
| 品牌光晕背景 | `radial-gradient(circle, rgba(59,130,246,.15) 0%, transparent 60%)` |
| 品牌光晕动画 | `pulse 8s ease-in-out infinite`（scale 1→1.1，opacity .5→.8） |
| 品牌 mark（登录页） | `48×48px`，`border-radius: 16px` |
| 品牌 mark（侧边栏） | `36×36px`，`border-radius: 13px` |
| 品牌标题（登录页） | `24px`，`font-weight: 850`，`color: white` |
| 品牌副标题 | `13px`，`color: #94A3B8` |

### 2.3 圆角

| 令牌 | 值 | 用途 |
|------|-----|------|
| `--radius` | `18px` | 卡片、面板、大容器、登录外壳 |
| `--radius-sm` | `12px` | 输入框、按钮、小容器 |
| — | `16px` | 导航组、搜索框、页面区块卡片 |
| — | `14px` | 搜索框（顶栏） |
| — | `10px` | 图标容器、小标签、操作按钮 |
| — | `9px` | 客户 logo |
| — | `8px` | 提示框、小元素、复选框圆角 |
| — | `7px` | 热力图单元格 |
| — | `50%` | 头像、圆形元素 |
| — | `999px` | 药丸标签、折叠按钮 |

### 2.4 阴影

| 令牌 | 值 | 用途 |
|------|-----|------|
| `--shadow` | `0 14px 40px rgba(15,23,42,.08)` | 卡片默认阴影（原型） |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,.04)` | 页面区块卡片阴影（实际开发） |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,.08)` | 中等阴影 |
| — | `0 4px 14px rgba(15,23,42,.04)` | 搜索框等轻量阴影 |
| — | `0 8px 20px rgba(29,78,216,.25)` | 主按钮阴影 |
| — | `0 12px 28px rgba(29,78,216,.35)` | 主按钮 hover 阴影 |
| — | `0 10px 28px rgba(37,99,235,.34)` | 品牌标识 `.mark` 阴影 |

### 2.5 字体

| 属性 | 值 |
|------|-----|
| 字体栈 | `Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif` |
| 基础字号 | `14px` |
| 基础行高 | `1.45` |

| 场景 | 字号 | 字重 |
|------|------|------|
| 品牌标识（.mark 内文字） | 20px / 侧边栏 16px | 900 |
| 页面大标题 | 24-28px | 700-800 |
| 品牌标题 | 24px / 侧边栏 16px | 850 |
| 卡片标题 / 区块标题 | 15-17px | 600-700 |
| 表单字段标题 | 28px（登录欢迎） | 800 |
| 表单标签 | 13px | 600 |
| 正文 / 表格内容 | 14px | 400 |
| 辅助说明 / 标签 | 12-13px | 400-500 |
| 数值大 KPI | 22-28px | 850 |
| 数值小 KPI | 18px | 700 |
| 小标签 / 分组标题 | 10-12px | 850（大写 + letter-spacing: .08em） |

---

## 3. 组件规范

### 3.1 卡片（Card）

```css
background: var(--panel);        /* #FFFFFF */
border: 1px solid var(--line);   /* #DBE3EF */
border-radius: 16px;             /* 页面区块统一 16px */
box-shadow: 0 1px 2px rgba(0,0,0,.04);
padding: 18px;
```

**卡片内边距变体**：

| 变体 | padding | 使用场景 |
|------|---------|----------|
| `pad` | `18px` | 常规卡片内容区 |
| `mini` | `11px` | KPI 条内紧凑卡片 |
| KPI 统计 | `16px` | 指标卡片 |

### 3.2 登录页组件

#### 3.2.1 登录外壳

```css
display: grid;
grid-template-columns: 480px 520px;
max-width: 1000px;
width: 100%;
min-height: 600px;
background: var(--panel);
border-radius: var(--radius);      /* 18px */
box-shadow: var(--shadow);
overflow: hidden;
```

#### 3.2.2 品牌侧

```css
background: radial-gradient(circle at 20% 0%, rgba(37,99,235,.28), transparent 32%),
            linear-gradient(180deg, #111C33 0%, #0B1220 100%);
color: #CBD5E1;
padding: 48px 40px;
display: flex;
flex-direction: column;
justify-content: space-between;
position: relative;
overflow: hidden;
```

#### 3.2.3 表单侧

```css
padding: 48px 56px;
display: flex;
flex-direction: column;
justify-content: center;
background: var(--panel);
```

#### 3.2.4 表单字段

| 组件 | 样式 |
|------|------|
| 表单标题 | `font-size: 28px; font-weight: 800; color: var(--ink); margin-bottom: 8px;` |
| 表单描述 | `color: var(--muted); font-size: 14px; margin-bottom: 36px;` |
| 字段容器 | `display: flex; flex-direction: column; gap: 8px;` |
| 表单标签 | `font-size: 13px; font-weight: 600; color: var(--ink);` |
| 输入框 | `width: 100%; padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; font-size: 14px;` |
| 输入框 focus | `outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(29,78,216,.1);` |
| 输入框 placeholder | `color: #94a3b8;` |
| 表单选项行 | `display: flex; align-items: center; justify-content: space-between; font-size: 13px;` |
| 表单底部 | `margin-top: 32px; text-align: center; color: var(--muted); font-size: 13px;` |

#### 3.2.5 复选框

```css
width: 16px;
height: 16px;
border: 1.5px solid var(--line);
border-radius: 4px;
cursor: pointer;
transition: all .2s ease;
/* checked */
background: var(--primary);
border-color: var(--primary);
```

#### 3.2.6 分隔线

```css
display: flex;
align-items: center;
gap: 12px;
color: var(--muted);
font-size: 12px;
margin: 8px 0;
/* 伪元素生成左右线条 */
::before, ::after { content: ''; flex: 1; height: 1px; background: var(--line); }
```

#### 3.2.7 特性展示

| 组件 | 样式 |
|------|------|
| 特性项 | `display: flex; gap: 16px; align-items: flex-start;` |
| 特性图标容器 | `width: 40px; height: 40px; border-radius: 10px; background: rgba(59,130,246,.15); flex-shrink: 0;` |
| 特性图标 SVG | `width: 20px; height: 20px; stroke: #3B82F6; fill: none; stroke-width: 2;` |
| 特性标题 | `color: white; font-size: 15px; font-weight: 700; margin-bottom: 4px;` |
| 特性描述 | `color: #94A3B8; font-size: 13px; line-height: 1.5;` |
| 版权信息 | `color: #64748B; font-size: 12px; text-align: center;` |

### 3.3 按钮

| 类型 | 样式 |
|------|------|
| 主按钮 | `background: linear-gradient(135deg, #1D4ED8, #2563EB); color: white; border-radius: 12px; box-shadow: 0 8px 20px rgba(29,78,216,.25); padding: 9px 12px; border: none;` |
| 主按钮 hover | `transform: translateY(-1px); box-shadow: 0 12px 28px rgba(29,78,216,.35);` |
| 主按钮 active | `transform: translateY(0);` |
| 次按钮 | `background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px;` |
| 次按钮 hover | `background: var(--soft);` |
| 表单主按钮 | `width: 100%; padding: 13px 20px;` + 同上渐变 |
| 表单次按钮 | `width: 100%; padding: 13px 20px; background: var(--bg); color: var(--ink); border: 1px solid var(--line);` |
| 侧边栏按钮 | `background: transparent; color: #CBD5E1; border-radius: 12px; padding: 8px 10px;` |
| 侧边栏 active | `background: linear-gradient(90deg, rgba(59,130,246,.24), rgba(6,182,212,.12)); color: white; box-shadow: inset 0 0 0 1px rgba(125,211,252,.12);` |
| 侧边栏 active 图标 | `color: #67E8F9` |
| 链接 | `color: var(--primary); text-decoration: none; font-weight: 500;` |
| 按钮组合 | `display: flex; gap: 8px; flex-wrap: wrap;` |

### 3.4 输入框

```css
padding: 12px 14px;
border: 1px solid var(--line);
border-radius: 12px;
font-size: 14px;
color: var(--ink);
/* focus */
border-color: var(--primary);
box-shadow: 0 0 0 3px rgba(29,78,216,.1);
```

### 3.5 搜索框（顶栏）

```css
flex: 1;
display: flex;
align-items: center;
gap: 10px;
background: white;
border: 1px solid var(--line);
border-radius: 14px;
padding: 10px 12px;
box-shadow: 0 4px 14px rgba(15,23,42,.04);
```

### 3.6 状态标签

| 状态 | 类名 | 背景 | 文字颜色 | 用途 |
|------|------|------|----------|------|
| 成功/健康 | `.tag.green` | `rgba(5,150,105,.10)` | `#047857` / `#059669` | 正常、正增长 |
| 预警/待处理 | `.tag.amber` | `rgba(217,119,6,.10)` | `#B45309` / `#D97706` | 临期、余额偏低 |
| 危险/异常 | `.tag.red` | `rgba(220,38,38,.10)` | `#B91C1C` / `#DC2626` | 失败、逾期、不足 |
| 信息/同步 | `.tag.blue` | `#DBEAFE` | `#1D4ED8` | 同步中、进行中 |
| 特殊分类 | `.tag.violet` | `#EDE9FE` | `#6D28D9` | 画像标签、包年客户 |
| 默认 | `.tag.gray` / `.tag` | `#F1F5F9` | `#475569` | 未激活、未知 |

```css
display: inline-flex;
border-radius: 999px;
padding: 4px 8px;
font-size: 12px;
font-weight: 700;
```

### 3.7 药丸标签（Pill）

```css
display: inline-flex;
align-items: center;
gap: 6px;
border: 1px solid var(--line);
background: white;
border-radius: 999px;
padding: 8px 11px;
color: var(--muted);
white-space: nowrap;
```

### 3.8 品牌标识（.mark）

| 场景 | 尺寸 | 圆角 | 字号 | 字重 |
|------|------|------|------|------|
| 侧边栏 | `36×36px` | `13px` | `16px` | `900` |
| 登录页 | `48×48px` | `16px` | `20px` | `900` |

```css
background: linear-gradient(135deg, #3B82F6, #06B6D4);
color: white;
display: grid;
place-items: center;
box-shadow: 0 10px 28px rgba(37,99,235,.34);
flex-shrink: 0;
```

### 3.9 头像

```css
width: 34px; height: 34px;
border-radius: 50%;
background: #DBEAFE;
color: #1D4ED8;
display: grid;
place-items: center;
font-weight: 800;
```

**头像尺寸变体**：

| 尺寸 | 使用场景 |
|------|----------|
| `34×34px` | 顶栏头像 |
| `80×80px` | 个人信息页头像 |

### 3.10 客户 Logo

```css
width: 30px;
height: 30px;
border-radius: 9px;
background: #E0F2FE;
color: #0369A1;
display: grid;
place-items: center;
font-weight: 850;
flex-shrink: 0;
```

### 3.11 图标

- **统一规范**：内联 SVG，`stroke` 描边风格，`fill: none`，`stroke-width: 2`
- 侧边栏图标：`18×18px`（一级）/ `14×14px`（二级）/ `20×20px`（折叠态一级）
- 顶栏搜索图标：`18×18px`
- SVG `stroke-linecap: round; stroke-linejoin: round`

### 3.12 统计卡片（StatCard / KPI Card）

| 属性 | 值 |
|------|-----|
| 背景 | `white` |
| 边框 | `1px solid var(--line)` |
| 圆角 | `16px` |
| 阴影 | `0 1px 2px rgba(0,0,0,.04)` |
| 内边距 | `16px`（紧凑 `11px`） |
| 标题字号 | `13px`，`color: var(--muted)` |
| 数值字号 | `22-28px`，`font-weight: 850` |

KPI 卡片布局：

| 变体 | 布局 |
|------|------|
| `default`（`.metric`） | 标题在上，指标值在下，趋势行在底部 |
| `compact`（`.mini`） | 标题 + 数值 + 描述垂直堆叠，高度更紧凑 |

### 3.13 KPI 条（KpiStrip）

多指标横向排列容器：

```css
display: grid;
grid-template-columns: repeat(6, 1fr);  /* 大屏 6 列 */
gap: 10px;
/* 响应式：≤1100px 切换为 repeat(2, 1fr) */
```

### 3.14 Hero 区

首页首屏两栏布局：

```css
display: grid;
grid-template-columns: 1.35fr .65fr;   /* 左宽右窄 */
gap: 18px;
margin-bottom: 18px;
```

### 3.15 空状态（EmptyState）

```css
padding: 48px 24px;
text-align: center;
/* 图标 */
width: 64px; height: 64px;
color: var(--soft);
margin-bottom: 16px;
/* 标题 */
font-size: 16px; font-weight: 600;
color: var(--ink);
/* 描述 */
font-size: 14px;
color: var(--muted);
margin-bottom: 24px;
/* 操作区 */
display: flex; gap: 12px;
```

### 3.16 操作按钮（ActionButton）

| 场景 | 样式 |
|------|------|
| 主操作 | `padding: 9px 12px; background: var(--primary); color: white; border-radius: 12px; border: none;` |
| 次操作 | `padding: 9px 12px; background: white; border: 1px solid var(--line); border-radius: 12px;` |
| 小表格内操作 | `padding: 4px 10px; font-size: 12px;` |
| 按钮 hover | `border-color: #93C5FD; background: #EFF6FF;` |
| 主按钮 hover | `background: #1E40AF;` |

### 3.17 输入框和表单状态

| 状态 | 边框 | 阴影 | 备注 |
|------|------|------|------|
| default | `1px solid var(--line)` | — | — |
| hover | — | — | 需补充 |
| focus | `1px solid var(--primary)` | `0 0 0 3px rgba(29,78,216,.1)` | ring 效果 |
| error | `1px solid var(--red)` | `0 0 0 3px rgba(220,38,38,.1)` | 需补充 |
| disabled | `background: var(--bg)` | — | cursor: not-allowed |

### 3.18 分页组件（Pagination）

```css
display: flex;
align-items: center;
gap: 8px;
/* 选页按钮 */
padding: 4px 10px;
font-size: 12px;
border: 1px solid var(--line);
background: white;
border-radius: 12px;
cursor: pointer;
/* 页码信息 */
font-size: 12px;
color: var(--muted);
```

### 3.19 表格（Table）

#### 3.19.1 表格容器

```css
overflow: auto;
border: 1px solid var(--line);
border-radius: 15px;
```

#### 3.19.2 表格本体

```css
width: 100%;
border-collapse: collapse;
min-width: 860px;
background: white;
/* 表头 */
th {
  padding: 12px;
  background: #F8FAFC;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  position: sticky;
  top: 0;
  border-bottom: 1px solid #EDF2F7;
}
/* 表格体 */
td {
  padding: 12px;
  border-bottom: 1px solid #EDF2F7;
  text-align: left;
  white-space: nowrap;
}
tr:hover td {
  background: #F8FBFF;
}
```

#### 3.19.3 客户信息组合（Customer Cell）

```css
display: flex;
align-items: center;
gap: 10px;
/* Logo */
.customer .logo { /* 参见 3.10 */ }
```

### 3.20 进度条 / 消耗条

```css
/* 容器 */
height: 8px;
background: #E2E8F0;
border-radius: 999px;
overflow: hidden;
/* 填充 */
display: block;
height: 100%;
border-radius: 999px;
background: linear-gradient(90deg, #2563EB, #06B6D4);
/* 动态宽度 */
width: XX%;  /* 内联 style 控制 */
```

### 3.21 图表组件

#### 3.21.1 SVG 图表容器

```css
height: 260px;
border: 1px solid #EDF2F7;
border-radius: 15px;
background: linear-gradient(180deg, #fff, #f8fafc);
position: relative;
overflow: hidden;
```

#### 3.21.2 图例

```css
display: grid;
gap: 8px;
/* 图例项 */
.legend div {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}
/* 色块 */
.sw {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
```

#### 3.21.3 环形图（Donut）

```css
width: 210px;
height: 210px;
border-radius: 50%;
/* 使用 conic-gradient 实现分段 */
background: conic-gradient(...);
margin: auto;
position: relative;
/* 中心白色圆 */
::after {
  content: "";
  position: absolute;
  inset: 45px;
  border-radius: 50%;
  background: white;
}
```

#### 3.21.4 柱状图（Bar Chart placeholder）

```css
display: flex;
align-items: flex-end;
gap: 10px;
height: 210px;
padding: 18px;
/* 单个柱 */
i {
  flex: 1;
  border-radius: 9px 9px 0 0;
  background: linear-gradient(180deg, #60A5FA, #1D4ED8);
  min-width: 16px;
}
```

#### 3.21.5 图表占位符

```css
/* 用于开发中/未完成图表 */
.chart-placeholder {
  padding: 40px 20px;
  text-align: center;
  color: var(--muted);
  background: var(--bg);
  border-radius: 12px;
  font-size: 13px;
}
```

### 3.22 热力图（Heatmap）

```css
/* 容器 */
display: grid;
grid-template-columns: repeat(7, 1fr);
gap: 6px;
/* 单元格 */
height: 26px;
border-radius: 7px;
background: #DBEAFE;
/* 颜色深度按倍数变化 */
:nth-child(3n) { background: #93C5FD; }
:nth-child(5n) { background: #1D4ED8; }
```

### 3.23 时间线 / 事件列表（Timeline）

```css
/* 时间线容器 */
display: grid;
gap: 10px;
/* 事件项 */
.event {
  display: grid;
  grid-template-columns: 82px 1fr auto;  /* 时间 - 内容 - 状态 */
  gap: 10px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #EDF2F7;
}
```

### 3.24 提示框（Callout）

```css
border-left: 4px solid var(--primary);
background: #EFF6FF;
border-radius: 14px;
padding: 14px;
color: #1E3A8A;
```

### 3.25 折叠列表 / 键值对（Compact List）

```css
/* 容器 */
display: grid;
gap: 9px;
/* 行 */
.row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid #EDF2F7;
  padding-bottom: 8px;
}
.row:last-child { border-bottom: 0; }
```

### 3.26 信息架构卡片（Information Architecture）

```css
/* 5 列布局 */
.ia {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  /* 卡片 */
  .card { padding: 14px; }
  .card h3 { margin: 0 0 8px; font-size: 15px; }
  .card ul { margin: 0; padding-left: 18px; color: var(--muted); font-size: 13px; }
}
/* 响应式：≤1100px 切换 1 列 */
```

### 3.27 原型框（Wire / Prototype Note）

```css
/* 容器 */
display: grid;
grid-template-columns: repeat(3, 1fr);
gap: 12px;
/* 虚线框 */
border: 1px dashed #BFDBFE;
border-radius: 16px;
padding: 12px;
background: #F8FBFF;
```

### 3.28 筛选区域（Filter Section）

```css
display: flex;
gap: 8px;
flex-wrap: wrap;
margin-bottom: 12px;
/* 筛选项 */
.field {
  min-width: 132px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  padding: 9px 10px;
  color: var(--muted);
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
```

### 3.29 标签页（Tabs）

```css
display: flex;
gap: 6px;
flex-wrap: wrap;
/* 标签项 */
.tab {
  border: 1px solid var(--line);
  background: white;
  border-radius: 999px;
  padding: 7px 10px;
  color: var(--muted);
  font-weight: 700;
}
.tab.active {
  background: #DBEAFE;
  border-color: #BFDBFE;
  color: #1D4ED8;
}
```

### 3.30 区块标题（Section Title）

```css
display: flex;
justify-content: space-between;
align-items: center;
margin: 4px 0 12px;
/* 标题 */
h2 {
  font-size: 17px;
  margin: 0;
}
/* 右侧操作区 */
display: flex;
gap: 8px;
```

### 3.31 辅助文本

```css
.color: var(--muted);
font-size: 12-13px;
```

---

## 4. 页面级组件规范

### 4.1 页面头部（PageHeader）

所有页面统一结构：

```
┌──────────────────────────────────────────────┐
│  页面标题                [搜索/操作按钮组]    │
│  页面副标题                                   │
└──────────────────────────────────────────────┘
```

```css
/* 容器 */
display: flex;
justify-content: space-between;
align-items: flex-start;
margin-bottom: 24px;
/* eyebow（小标题） */
color: var(--primary);
font-weight: 800;
font-size: 12px;
letter-spacing: .08em;
text-transform: uppercase;
/* 页面标题 */
.h1 {
  font-size: 26px;
  font-weight: 850;
  margin: 4px 0;
}
/* 副标题 */
.desc {
  color: var(--muted);
  margin: 0;
  max-width: 760px;
}
/* 操作按钮组 */
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
```

### 4.2 筛选区域（FilterSection）

```css
background: white;
padding: 24px;
border-radius: 16px;
border: 1px solid var(--line);
box-shadow: 0 1px 2px rgba(0,0,0,.04);
margin-bottom: 24px;
```

筛选项使用 `a-form layout="inline"`，各筛选项宽度统一（如 `width: 200px`）。

### 4.3 表格区域（TableSection）

```css
background: white;
border-radius: 16px;
border: 1px solid var(--line);
box-shadow: 0 1px 2px rgba(0,0,0,.04);
overflow: hidden;
/* 表头 */
.arco-table th {
  background: var(--bg);
  color: #334155;
  font-weight: 600;
  font-size: 12px;
}
/* 行 hover */
.arco-table tr:hover td {
  background: #F8FBFF;
}
```

### 4.4 图表卡片（ChartCard）

```css
background: white;
border-radius: 16px;
border: 1px solid var(--line);
box-shadow: 0 1px 2px rgba(0,0,0,.04);
padding: 20px;
/* 标题 */
.section-title h2 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}
```

### 4.5 标签页（Tabs）

客户详情页等使用标签页切换内容：

```css
/* 标签容器 */
.tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
/* 标签项 */
.tab {
  border: 1px solid var(--line);
  background: white;
  border-radius: 999px;
  padding: 7px 10px;
  color: var(--muted);
  font-weight: 700;
  font-size: 14px;
}
.tab.active {
  background: #DBEAFE;
  border-color: #BFDBFE;
  color: #1D4ED8;
}
```

### 4.6 批量操作工具栏（BatchToolbar）

表格多选后出现的操作栏：

```css
margin-bottom: 16px;
padding: 12px 16px;
background: rgba(29,78,216,.06);
border: 1px solid rgba(29,78,216,.15);
border-radius: 12px;
display: flex; align-items: center; gap: 12px;
/* 选中数 */
font-size: 13px; color: var(--primary);
```

### 4.7 个人信息页

```
┌────────────────┬───────────────────────┐
│                │                       │
│   头像区域      │   基本信息表单         │
│   居中排列      │   键值对网格           │
│   含头像、姓名  │   用户名/邮箱/手机     │
│   角色、邮箱    │   角色/创建时间        │
│   编辑按钮      │   最后登录             │
│                │                       │
└────────────────┴───────────────────────┘
grid-template-columns: 1fr 1fr
```

**头像区样式**：
- 头像 `80×80px`，`border-radius: 50%`，`background: #DBEAFE`，`color: #1D4ED8`
- 姓名 `font-size: 18px; font-weight: 700`
- 辅助信息 `color: #94A3B8`

**基本信息区**：
- 字段网格 `display: grid; gap: 14px`
- 标签 `display: block; font-size: 12px; margin-bottom: 4px; color: var(--muted)`
- 值 `<b>` 标签加粗

### 4.8 重置密码页

```
┌──────────────────────────┐
│      居中卡片容器         │
│   max-width: 480px       │
│   图标 + 标题 + 描述      │
│   新密码输入框            │
│   确认密码输入框          │
│   提交按钮               │
└──────────────────────────┘
```

- 图标容器：`56×56px`，`border-radius: 14px`，`background: rgba(29,78,216,.10)`
- 标题：`font-size: 22px; font-weight: 700`
- 描述：`color: var(--muted); margin-bottom: 24px`
- 按钮：`width: 100%; margin-top: 8px`

### 4.9 结算单状态标签（InvoiceStatusBadge）

使用 Arco `a-tag` 组件，按状态映射颜色：

| 状态 | 文本 | 颜色 |
|------|------|------|
| draft | 草稿 | gray |
| pending_customer | 待客户确认 | orange |
| customer_confirmed | 客户已确认 | blue |
| paid | 已付款 | green |
| completed | 已完成 | arcoblue |
| cancelled | 已取消 | red |

### 4.10 自动完成输入（KeywordAutoComplete / CustomerAutoComplete）

用于筛选区的关键词输入，支持客户名称/ID 模糊匹配：

```css
width: 200px;   /* 可配置 */
/* 基于 a-auto-complete 或 a-input */
```

### 4.11 骨架屏（SkeletonCard）

数据加载时的占位：

```css
background: white;
border-radius: 16px;
border: 1px solid var(--line);
padding: 20px;
/* 内部骨架条 */
background: linear-gradient(90deg, var(--bg) 25%, var(--soft) 50%, var(--bg) 75%);
background-size: 200% 100%;
animation: shimmer 1.5s infinite;
border-radius: 4px;
```

### 4.12 结算单时间线（InvoiceTimeline）

展示结算单状态变更历史：

```css
/* 时间线容器 */
display: flex; flex-direction: column; gap: 16px;
/* 节点 */
display: flex; gap: 12px;
/* 圆点 */
width: 8px; height: 8px;
border-radius: 50%;
background: var(--primary);
/* 连接线 */
width: 2px;
background: var(--line);
/* 时间文字 */
font-size: 12px; color: var(--muted);
/* 内容文字 */
font-size: 14px; color: var(--ink);
```

---

## 5. 布局系统

### 5.1 整体框架

```
┌──────────┬──────────────────────────────┐
│          │  顶部栏（sticky, 毛玻璃）      │
│  侧边栏   ├──────────────────────────────┤
│  252px   │                              │
│  可折叠   │  主内容区                      │
│  → 72px  │  max-width: 1440px           │
│          │  padding: 22px 24px 44px      │
│          │                              │
└──────────┴──────────────────────────────┘
```

**核心实现（基于 CSS Grid）**：

```css
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 252px 1fr;
  transition: grid-template-columns .25s ease;
}
.shell.collapsed {
  grid-template-columns: 72px 1fr;
}
```

**定位**：
- 侧边栏：`position: sticky; top: 0; height: 100vh;` — 始终跟随视口
- 顶部栏：`sticky`，`backdrop-filter: blur(14px)`，`background: rgba(246,248,251,.86)`
- 主内容区：`max-width: 1440px`，`margin: 0 auto`

### 5.2 登录页

```
┌────────────────┬──────────────────┐
│                │                  │
│  品牌展示区     │  登录表单区       │
│  480px         │  520px           │
│  深色渐变背景   │  白色背景         │
│                │                  │
└────────────────┴──────────────────┘
max-width: 1000px, min-height: 600px, border-radius: 18px, shadow
```

### 5.3 内容区典型布局

| 页面类型 | 布局模式 |
|----------|----------|
| 仪表盘 | Hero 区（1.35fr + .65fr）→ KPI 行（6 列）→ 图表/表格 |
| 列表页 | 筛选条 → 指标行 → 表格 |
| 详情页 | 头部 KPI（4 列）→ Tab 切换 → 各区块卡片 |
| 分析页 | 筛选 → KPI 条 → 图表 → 排行表 |
| 个人/认证 | 单列居中 或 左右分栏 |

### 5.4 网格布局参考

| 类名 | 网格定义 | 间隙 |
|------|----------|------|
| `.grid-4` | `repeat(4, 1fr)` | `14px` |
| `.grid-3` | `repeat(3, 1fr)` | `14px` |
| `.grid-2` | `repeat(2, 1fr)` | `14px` |
| `.kpi-strip` | `repeat(6, 1fr)` | `10px` |
| `.hero` | `1.35fr .65fr` | `18px` |
| `.ia` | `repeat(5, 1fr)` | `12px` |
| `.prototype-note` | `repeat(3, 1fr)` | `12px` |

**响应式**：
- `≤ 1100px`：`.grid-4/.grid-3/.grid-2/.hero/.ia/.prototype-note` 切换为 `1fr`；`.kpi-strip` 切换为 `repeat(2, 1fr)`
- `≤ 640px`：`.kpi-strip` 切换为 `1fr`；`.metric .value` 字号缩小至 `22px`

### 5.5 间距

| 场景 | 值 |
|------|-----|
| 页面内边距 | `22px 24px 44px` |
| 卡片内边距 | `18-24px` |
| 卡片间距 | `14-18px`（常用 `14px`） |
| 侧边栏内边距 | `16px 12px 14px` |
| 表单侧内边距 | `48px 56px` |
| 元素间距（通用） | `4px / 6px / 8px / 10px / 12px / 14px / 16px` |

---

## 6. 侧边栏导航

### 6.1 结构

| 分组 | 一级菜单 | 二级菜单 |
|------|----------|----------|
| **总览** | 设计总览、运营工作台 | — |
| **核心功能** | 客户管理（筛选/360/分类）、结算管理（充值/配置/队列） | 客户列表、客户详情、标签管理；余额管理、计费规则、结算单 |
| **运营分析** | 客户分析（趋势/进度/预警/分布/智能） | 消耗分析、回款分析、健康度、画像分析、预测回款 |
| **系统管理** | 系统治理（账号/权限/监控/追溯） | 用户管理、角色管理、同步日志、审计日志 |
| **个人** | 个人信息、重置密码 | — |

### 6.2 导航组件样式

#### 6.2.1 导航容器（.nav）

```css
flex: 1;
min-height: 0;
display: flex;
flex-direction: column;
gap: 7px;
overflow-y: auto;
overflow-x: visible;
```

#### 6.2.2 导航组（.nav-group）

```css
display: grid;
gap: 4px;
overflow: visible;
border: 1px solid rgba(148,163,184,.10);
border-radius: 16px;
padding: 6px;
background: rgba(15,23,42,.20);
```

#### 6.2.3 分组标题（.nav-title）

```css
padding: 2px 9px 1px;
color: #93A4B8;
font-size: 10px;
font-weight: 850;
letter-spacing: .08em;
text-transform: uppercase;
```

#### 6.2.4 一级菜单按钮

```css
border: 0;
background: transparent;
color: #CBD5E1;
text-align: left;
padding: 8px 10px;
border-radius: 12px;
display: flex;
gap: 10px;
align-items: center;
min-height: 34px;
transition: background .18s ease, color .18s ease, box-shadow .18s ease, transform .18s ease;
/* hover */
:hover {
  background: rgba(255,255,255,.09);
  color: white;
}
/* active */
.active {
  background: linear-gradient(90deg, rgba(59,130,246,.24), rgba(6,182,212,.12));
  color: white;
  box-shadow: inset 0 0 0 1px rgba(125,211,252,.12);
}
.active .nav-icon { color: #67E8F9; }
```

#### 6.2.5 折叠态一级菜单按钮

```css
/* 折叠态按钮尺寸 */
.shell.collapsed .nav button {
  width: 40px;
  height: 40px;
  min-height: 40px;
  padding: 0;
  justify-content: center;
  border-radius: 14px;
}
/* 折叠态隐藏文字 */
.shell.collapsed .nav-text,
.shell.collapsed .chev,
.shell.collapsed .nav-hint { display: none; }
/* 折叠态图标放大 */
.shell.collapsed .nav-icon { width: 20px; height: 20px; }
.shell.collapsed .nav-icon svg { width: 20px; height: 20px; }
```

#### 6.2.6 侧边栏折叠按钮

```css
position: absolute;
top: 22px;
right: -17px;
width: 34px;
height: 34px;
z-index: 80;
border: 1px solid rgba(147,197,253,.24);
background: linear-gradient(135deg, #1D4ED8, #0891B2);
color: white;
border-radius: 999px;
padding: 0;
cursor: pointer;
display: grid;
place-items: center;
font-weight: 900;
box-shadow: 0 10px 26px rgba(15,23,42,.30);
transition: background .18s ease, color .18s ease, box-shadow .18s ease, transform .18s ease;
/* hover */
:hover {
  transform: translateX(2px);
  box-shadow: 0 12px 30px rgba(37,99,235,.38);
}
/* 箭头旋转 */
.collapsed .toggle-icon {
  transform: rotate(180deg);
}
```

#### 6.2.7 侧边栏说明卡片

```css
display: block;
border: 1px solid rgba(147,197,253,.16);
background: rgba(15,23,42,.38);
border-radius: 15px;
padding: 10px 11px;
color: #DBEAFE;
font-size: 12px;
line-height: 1.45;
```

### 6.3 交互规则

- 一级菜单负责业务域分组，二级菜单负责具体任务入口
- 所有菜单配备统一 SVG 图标；文字包裹为 `.nav-text`，折叠态隐藏
- 二级菜单右侧短标签（`.nav-hint`）提示任务属性（筛选/360/分类/充值/配置/队列/趋势/进度/预警/分布/智能/账号/权限/监控/追溯）
- 展开态父级菜单单展开逻辑（手风琴）：点击父级切换自身 `aria-expanded`
- 折叠态点击父级直接进入对应页面（`.show(page)`）
- **重要**：切换二级菜单页面时，当前域二级菜单保持展开状态（通过 `data-page` 属性联动）
- **折叠态强制隐藏所有二级菜单**：

```css
.shell.collapsed .subnav,
.shell.collapsed .nav-parent[aria-expanded="true"] + .subnav {
  display: none !important;
}
.shell.collapsed .subnav button {
  display: none !important;
}
```

### 6.4 折叠/展开状态表

| 属性 | 展开态 | 折叠态 |
|------|--------|--------|
| 宽度 | `252px` | `72px` |
| 显示内容 | 品牌文字、分组标题、一/二级菜单、标签、说明卡片 | 仅一级菜单图标 |
| 隐藏内容 | — | 品牌文字、分组标题、二级菜单、标签、菜单文字、说明 |
| 二级菜单 | 正常展开/折叠 | **强制隐藏（!important）** |
| 当前域高亮 | 二级菜单高亮 | 父级一级菜单高亮 |
| 持久化 | `localStorage` 保存 `prototype-sidebar-collapsed` 状态 |

**折叠态导航组样式**：

```css
.shell.collapsed .nav-group {
  width: 44px;
  padding: 0;
  border-color: transparent;
  background: transparent;
  border-radius: 14px;
  gap: 6px;
}
```

### 6.5 侧边栏滚动（垂直内容溢出处理）

当功能菜单数量过多导致侧边栏内容超出视口高度时，需要支持垂直滚动且不裁剪二级菜单：

```css
/* 侧边栏容器：sticky 定位，保持可见 */
.side {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: visible;        /* 关键：允许内容溢出 */
}

/* 导航区：支持垂直滚动 */
.nav {
  flex: 1;
  min-height: 0;            /* 关键：允许 flex 子项收缩 */
  display: flex;
  flex-direction: column;
  overflow-y: auto;         /* 垂直滚动 */
  overflow-x: visible;      /* 关键：防止二级菜单被裁剪 */
}

/* 导航组：确保二级菜单可见 */
.nav-group {
  overflow: visible;        /* 关键：防止子菜单被裁剪 */
}

/* 子导航容器 */
.subnav {
  display: none;
  gap: 1px;
  margin: 0 0 2px 17px;
  padding-left: 8px;
  border-left: 1px solid rgba(148,163,184,.22);
}

/* 父级展开时显示子导航 */
.nav-parent[aria-expanded="true"] + .subnav {
  display: grid;
}
```

**核心要点**：
1. `.side` 使用 `position: sticky` + `height: 100vh`，不设置 `overflow: hidden`
2. `.nav` 设置 `overflow-y: auto` 实现滚动，配合 `min-height: 0` 使 flex 子项正确收缩
3. `.nav-group` 和 `.subnav` 保持 `overflow: visible`，确保二级菜单不被裁剪
4. 开发时必须验证：菜单项过多时侧边栏垂直可滚动，同时展开的二级菜单能完整显示

---

## 7. 交互规范

### 7.1 页面切换逻辑

```javascript
function show(id) {
  // 1. 切换页面显示
  pages.forEach(p => p.classList.toggle('active',
    p.id === id || (id === 'consumption' && p.id === 'analytics')));
  
  // 2. 激活对应叶子节点
  leafButtons.forEach(b => b.classList.toggle('active',
    b.dataset.page === id || (id === 'consumption' && b.dataset.page === 'analytics')));
  
  // 3. 激活对应父节点并保持展开状态
  parents.forEach(p => {
    const active = p.dataset.page === id
      || (id === 'detail' && p.dataset.page === 'customers')
      || (id === 'consumption' && p.dataset.page === 'analytics');
    p.classList.toggle('active', active);
    if (!shell.classList.contains('collapsed')) {
      p.setAttribute('aria-expanded', String(active));
    }
  });
  
  // 4. URL hash 同步
  location.hash = id;
  
  // 5. 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
```

### 7.2 侧边栏状态持久化

```javascript
// 切换折叠/展开
function setSidebarCollapsed(collapsed) {
  shell.classList.toggle('collapsed', collapsed);
  toggle.setAttribute('aria-expanded', String(!collapsed));
  toggle.setAttribute('aria-label', collapsed ? '展开侧边栏' : '折叠侧边栏');
  toggle.title = collapsed ? '展开侧边栏' : '折叠侧边栏';
  if (toggleLabel) toggleLabel.textContent = collapsed ? '展开' : '收起';
  localStorage.setItem('prototype-sidebar-collapsed', String(collapsed));
}

// 初始化读取
setSidebarCollapsed(localStorage.getItem('prototype-sidebar-collapsed') === 'true');
```

### 7.3 手风琴交互

```javascript
parents.forEach(p => p.addEventListener('click', e => {
  e.stopPropagation();
  // 折叠态：直接进入页面
  if (shell.classList.contains('collapsed')) {
    show(p.dataset.page);
    return;
  }
  // 展开态：切换自身二级菜单
  const isOpen = p.getAttribute('aria-expanded') === 'true';
  parents.forEach(other => other.setAttribute('aria-expanded',
    String(other === p && !isOpen)));
}));
```

### 7.4 继承导航（data-page-link）

页面内链接可通过 `data-page-link` 属性触发导航：

```html
<button data-page-link="detail">查看详情</button>
```

```javascript
document.querySelectorAll('[data-page-link]')
  .forEach(b => b.addEventListener('click', () => show(b.dataset.pageLink)));
```

### 7.5 全局快捷键

- `/`：聚焦搜索框
- `Enter`（非按钮聚焦时）：提交表单

---

## 8. 动效

| 场景 | 动效 |
|------|------|
| 侧边栏折叠/展开 | `transition: .25s ease`（grid-template-columns） |
| 折叠态内容显隐 | `opacity .16s ease, transform .16s ease, visibility .16s ease` |
| 导航 chevron 旋转 | `transform .18s ease`，`rotate(180deg)` |
| 折叠按钮 hover | `transform: translateX(2px)`，`box-shadow` 增强 |
| 主按钮 hover | `transform: translateY(-1px)`，`box-shadow` 增强 |
| 主按钮 active | `transform: translateY(0)` |
| 次按钮 hover | `background: var(--soft)` |
| 输入框 focus | `border-color` + `box-shadow: 0 0 0 3px rgba(29,78,216,.1)` |
| 登录页品牌区光晕 | `pulse 8s ease-in-out infinite` |
| 顶部栏 | `backdrop-filter: blur(14px)` 毛玻璃效果 |
| 骨架屏 | `shimmer 1.5s infinite` |
| 链接 hover | `color: var(--primary-2)` |

### 关键动画定义

```css
/* 登录页品牌光晕脉冲 */
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: .5; }
  50% { transform: scale(1.1); opacity: .8; }
}

/* 骨架屏闪烁 */
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 折叠按钮箭头旋转 */
.toggle-icon {
  transition: transform .25s ease;
}
.shell.collapsed .toggle-icon {
  transform: rotate(180deg);
}

/* 二级菜单展开/折叠指示器 */
.chev {
  transition: transform .18s ease;
  font-size: 10px;
}
.nav-parent[aria-expanded="true"] .chev {
  transform: rotate(180deg);
}

/* 导航文字渐隐 */
.nav-text, .nav-title, .nav-hint, .chev, .side-note, .brand > div:last-child {
  transition: opacity .16s ease, transform .16s ease, visibility .16s ease;
}

/* 导航按钮过渡 */
.nav button {
  transition: background .18s ease, color .18s ease, box-shadow .18s ease, transform .18s ease;
}
```

---

## 9. 响应式

| 断点 | 行为 |
|------|------|
| `> 1100px` | 正常双栏/多栏布局 |
| `≤ 1100px` | 侧边栏切换为顶部相对定位、双列导航网格；`.grid-4/.grid-3/.grid-2/.hero/.ia/.prototype-note` 切换为 `1fr`；`.kpi-strip` 切换 `repeat(2, 1fr)`；`desktop-only` 隐藏 |
| `≤ 960px` | 登录页切换单列（品牌区 + 表单区垂直堆叠，隐藏第 3+ 特性项） |
| `≤ 640px` | 登录页全屏无圆角；页面 padding 缩小至 `16px`；搜索框换行全宽；导航单列；KPI 条单列；`.metric .value` 字号缩小至 `22px`；`.nav-hint` 隐藏 |

### 关键响应式规则

```css
@media (max-width: 1100px) {
  .shell { grid-template-columns: 1fr; }
  .side {
    position: relative;
    height: auto;
    max-height: none;
    overflow-y: auto;
  }
  .nav {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    align-items: start;
  }
  .top { position: relative; }
}

@media (max-width: 960px) {
  .login-shell {
    grid-template-columns: 1fr;
    max-width: 520px;
  }
  .feature-item:nth-child(n+3) { display: none; }
}

@media (max-width: 640px) {
  body { padding: 0; }
  .login-shell {
    border-radius: 0;
    min-height: 100vh;
  }
  .form-side { padding: 32px 24px; }
}
```

---

## 10. 页面清单与功能概览

### 10.1 登录认证

| 页面 | 文件 | 功能 |
|------|------|------|
| 登录页 | `Login.vue` | 左右分栏登录：品牌展示 + 账号密码表单 + 忘记密码弹窗 + 企业 SSO |
| 重置密码 | `ResetPassword.vue` | 居中卡片：图标 + 新密码 + 确认密码 |

### 10.2 仪表盘

| 页面 | 文件 | 功能 |
|------|------|------|
| 首页 | `Home.vue` | 6 KPI 条 + 经营趋势图 + 异常与待办 + 优先跟进客户表格 |
| 仪表盘布局 | `Dashboard.vue` | 侧边栏 + 顶栏 + 路由出口 |
| 个人信息 | `Profile.vue` | 左右分栏：头像区 + 信息键值对 |
| 设计总览 | `Overview.vue` | 三栏卡片 + 信息架构 5 列 + 原型覆盖框 |

### 10.3 客户管理

| 页面 | 文件 | 功能 |
|------|------|------|
| 客户列表 | `customers/Index.vue` | 4 KPI 卡片 + 筛选 + 客户表格（含客户信息组合、进度条、标签） |
| 客户详情 | `customers/Detail.vue` | 4 KPI + 画像 + 消耗热力图 + 时间线 |
| 标签管理 | `tags/Index.vue` | 标签分组 Tab + 标签云展示 |

**客户列表组件**：
- `CustomerFilters.vue`：组合筛选（下拉选 + 按钮组）
- `CustomerTable.vue`：表格（客户 logo + 名称组合、健康度标签、消耗进度条）

**客户详情区块**：
- `CustomerProfileCard.vue`：画像键值对
- `CustomerHeatmap.vue`：30 天消耗热力图
- `CustomerTimeline.vue`：结算与操作记录时间线

### 10.4 结算管理

| 页面 | 文件 | 功能 |
|------|------|------|
| 余额管理 | `billing/Balance.vue` | 4 KPI + 筛选 + 余额表格 + 分页 |
| 计费规则 | `billing/PricingRules.vue` | 筛选 + 规则表格 |
| 结算单 | `billing/Invoices.vue` | 4 KPI + 筛选 + 结算单表格 + 分页 |

### 10.5 运营分析

| 页面 | 文件 | 功能 |
|------|------|------|
| 消耗分析 | `analytics/Consumption.vue` | 筛选 + 6 KPI 条 + 趋势图 + 环形分布图 + Top 排行表格 |
| 回款分析 | `analytics/Payment.vue` | 4 KPI 条 + 柱状对比图 + 饼图 + 趋势图 |
| 健康度分析 | `analytics/Health.vue` | 4 KPI + 预警客户列表 + 长期未消耗客户列表 |
| 画像分析 | `analytics/Profile.vue` | 4 KPI + 行业分布 + 规模等级分布 + 消费等级分布 + 房产占比 |
| 预测回款 | `analytics/Forecast.vue` | 筛选 + 4 KPI + 趋势图 + 明细表格 |

### 10.6 系统管理

| 页面 | 文件 | 功能 |
|------|------|------|
| 用户管理 | `users/Index.vue` | 搜索 + 用户表格 |
| 角色管理 | `roles/Index.vue` | 搜索 + 角色表格 + 权限按钮 |
| 同步日志 | `system/SyncLogs.vue` | 4 KPI + 筛选 + 任务记录表格 |
| 审计日志 | `system/AuditLogs.vue` | 筛选 + 操作记录表格 |

---

## 11. 图表组件规范

| 图表 | 组件 | 用途 |
|------|------|------|
| 余额趋势图 | `BalanceTrendChart.vue` | 客户详情页余额变化折线 |
| 消耗分布图 | `UsageDistributionChart.vue` | 设备类型消耗分布饼图/柱图 |
| 消费等级进度 | `ConsumeLevelProgress.vue` | 客户详情页消费等级进度条 |
| 健康度仪表盘 | `HealthGauge.vue` | 客户详情页健康度评分仪表 |

图表统一规范：
- 使用 ECharts 或 Arco Charts
- 颜色序列：`[#1D4ED8, #0891B2, #059669, #D97706, #DC2626, #7C3AED]`
- 背景透明，文字使用 `var(--muted)`
- 网格线使用 `var(--line)` 或更浅
- SVG 原型图表作为低保真占位，开发时替换为真实图表组件
- 图表占位符样式（开发中状态）：`padding: 40px 20px; text-align: center; color: var(--muted); background: var(--bg); border-radius: 12px`

---

## 12. 覆盖的原型页面

1. **登录页**（login.html）：左右分栏，品牌展示区（含脉冲光晕动画）+ 登录表单（账号密码 + 企业 SSO）
2. **设计总览**（index.html）：Hero 区 + 三栏卡片 + 信息架构 5 列 + 原型覆盖框
3. **运营工作台**（index.html）：6 KPI 条 + Hero 区（经营趋势图 + 异常待办）+ 优先跟进客户表格
4. **客户管理**（index.html）：4 KPI 卡片 + 筛选 + 客户表格（logo + 进度条 + 标签）
5. **客户详情**（index.html）：4 KPI + 画像卡 + 30 天热力图 + 时间线
6. **消耗分析**（index.html）：筛选 + 6 KPI + 趋势 SVG 图 + 环形图 + Top 排行表
7. **结算管理**（index.html）：4 KPI + 流程时间线 + 柱状图 + 账单队列表格
8. **系统治理**（index.html）：3 列卡片（角色权限矩阵、高风险操作、系统健康）+ 审计日志表格
9. **余额管理**（index.html）：4 KPI + 筛选 + 余额表格 + 分页
10. **计费规则**（index.html）：筛选 + 规则表格（定价/阶梯/包年）
11. **结算单**（index.html）：4 KPI + 筛选 + 结算单表格（金额/折扣/实付）+ 分页
12. **回款分析**（index.html）：筛选 + 4 KPI + 3 个图表占位
13. **健康度分析**（index.html）：4 KPI + 预警客户表 + 长期未消耗客户表
14. **画像分析**（index.html）：4 KPI + 2×2 图表网格（饼图/柱图/环形图）
15. **预测回款**（index.html）：筛选 + 4 KPI + 趋势图 + 明细表
16. **用户管理**（index.html）：搜索 + 用户表格
17. **角色管理**（index.html）：搜索 + 角色表格 + 权限按钮
18. **标签管理**（index.html）：分组 Tab + 标签云 + 分页
19. **同步日志**（index.html）：4 KPI + 筛选 + 任务记录表格
20. **审计日志**（index.html）：筛选 + 操作记录表格 + 分页
21. **个人信息**（index.html）：左右分栏（头像 + 基本信息键值对）
22. **重置密码**（index.html）：居中卡片（图标 + 新密码 + 确认密码）

---

## 13. 无障碍与可用性

| 要求 | 实现 |
|------|------|
| 侧边栏折叠状态 | `aria-expanded` + `aria-label` 同步更新 |
| 导航当前状态 | `aria-expanded="true/false"` 表达二级菜单状态 |
| 按钮 | 所有交互按钮可使用 Enter/Space 激活 |
| 表单 | `<label>` 关联 `<input for>` |
| 链接 | 可使用 Enter 激活 |
| 搜索框 | `role="search"` + `aria-label` |
| 键盘快捷键 | `/` 聚焦搜索框，`Enter` 触发表单提交 |
| 色彩对比 | 正文文字与背景对比度 ≥ 4.5:1，大文字对比度 ≥ 3:1 |
| 焦点可见性 | `focus` 态需有明显 outline/ring 提示 |

---

## 14. 落地建议

### 技术路线

- 保留 Vue 3 + Arco Design 组件体系
- 通过 Arco 主题变量 + 全局 CSS 自定义属性映射本规范令牌
- 优先统一布局、信息架构、CSS token 和图表配置，避免大规模替换组件库
- 建议使用 `vue-router` + `pinia` 管理页面状态和侧边栏折叠状态

### 优先级

- **P0**：首页 / 客户管理 / 消耗分析 / 结算管理
- **P1**：画像管理 / 健康度分析 / 回款分析
- **P2**：用户管理 / 角色管理 / 标签管理 / 日志

### 各页面补齐清单

- **表格页**：保存筛选、批量操作、异常优先排序、空状态说明、分页
- **分析页**：同步质量提示、图表解释、点击联动明细、导出报告
- **结算页**：生成前预检查、失败原因结构化、金额影响排序
- **详情页**：Drawer/侧栏承载预览，减少页面跳转

### 组件映射建议

| 本规范组件 | Arco Design 对应 |
|------------|-----------------|
| 卡片（Card） | `a-card` |
| 按钮（主/次） | `a-button` type="primary"/"outline" |
| 输入框 | `a-input` |
| 表格 | `a-table` |
| 标签页 | `a-tabs` |
| 标签（Tag） | `a-tag` |
| 分页 | `a-pagination` |
| 表单 | `a-form` |
| 下拉选择 | `a-select` |
| 日期范围 | `a-range-picker` |
| 徽标（Badge） | `a-badge` |
| 头像 | `a-avatar` |
| 信息卡片 | `a-statistic` |
| 抽屉（详情） | `a-drawer` |
| 弹窗（表单） | `a-modal` |
| 确认弹窗 | `a-popconfirm` |

---

## 附录：CSS 变量速查表

```css
:root {
  /* 中性色 */
  --bg: #F6F8FB;
  --panel: #FFFFFF;
  --ink: #0F172A;
  --muted: #475569;
  --soft: #E2E8F0;
  --line: #DBE3EF;

  /* 主色/语义色 */
  --primary: #1D4ED8;
  --primary-2: #2563EB;
  --cyan: #0891B2;
  --green: #059669;
  --amber: #D97706;
  --red: #DC2626;
  --violet: #7C3AED;

  /* 阴影 */
  --shadow: 0 14px 40px rgba(15, 23, 42, .08);
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, .04);

  /* 圆角 */
  --radius: 18px;
  --radius-sm: 12px;
}
```
 </longcat_think>

