# 前端 E2E 测试与功能验证计划

> **依据**: `docs/superpowers/plans/2026-07-11-frontend-refactoring-plan.md` Phase 10 验证清单
> **测试框架**: Playwright 1.59.1（已配置）
> **目标**: 22 个页面全覆盖 — 视觉规范 + 功能完整性 + 响应式 + 无障碍

---

## 1. 现有测试覆盖差距分析

### 1.1 已有测试文件（22 个文件，~120 个测试用例）

| 文件 | 用例数 | 覆盖深度 | 问题 |
|------|--------|----------|------|
| `test_login_flow.spec.ts` | 4 | ✅ 功能完整 | 无视觉断言 |
| `test_core_pages_rendering.spec.ts` | 11 | ⚠️ 浅层渲染 | 选择器过时、登录页 skip |
| `test_customer_crud.spec.ts` | 9 | ✅ 功能完整 | — |
| `customer-detail.spec.ts` | 17 | ✅ 功能完整 | — |
| `test_customer_filters.spec.ts` | 10 | ✅ 功能完整 | — |
| `test_customer_import_export.spec.ts` | 6 | ✅ 功能完整 | — |
| `test_customer_edge_cases.spec.ts` | 9 | ✅ 功能完整 | — |
| `test_customer_permissions.spec.ts` | 6 | ✅ 功能完整 | — |
| `test_customer_batch_edit.spec.ts` | ? | ✅ 功能完整 | — |
| `test_customer_management.spec.ts` | ? | ✅ 功能完整 | — |
| `test_billing_workflow.spec.ts` | 4 | ⚠️ 浅层 | 使用 `waitForTimeout` |
| `test_invoice_workflow.spec.ts` | 7 | ⚠️ 浅层 | 大量 `if isVisible` 守卫，断言弱 |
| `test_balance_recharge.spec.ts` | 8 | ✅ 功能完整 | 负数扣减测试好 |
| `test_balance_import.spec.ts` | 5 | ✅ 功能完整 | — |
| `test_analytics.spec.ts` | 13 | ⚠️ 中等 | 选择器可能过时 |
| `test_data_sync.spec.ts` | 11 | ✅ 功能完整 | Mock 完善 |
| `test_sync_task.spec.ts` | 5 | ⚠️ 选择器错误 | `input[name="username"]` 应为 `input[field="username"]` |
| `test_users.spec.ts` | 5 | 🔴 浅层 | 仅 URL 检查 + 条件守卫 |
| `test_roles.spec.ts` | 4 | ⚠️ 中等 | 权限配置测试好，其余浅层 |
| `test_tags.spec.ts` | 5 | 🔴 浅层 | 仅 URL 检查 + 条件守卫 |

### 1.2 完全缺失的页面（6 个）

| 页面 | 路由 | 文件 | 缺失内容 |
|------|------|------|----------|
| 重置密码 | `/reset-password` | `ResetPassword.vue` | 无任何测试 |
| 画像分析 | `/analytics/profile` | `analytics/Profile.vue` | 无任何测试 |
| 预测回款 | `/analytics/forecast` | `analytics/Forecast.vue` | 无任何测试 |
| 行业类型 | `/system/industry-types` | `system/IndustryTypes.vue` | 无任何测试 |
| 数据清空 | `/system/database-management` | `system/DatabaseManagement.vue` | 无任何测试 |
| 个人信息 | `/profile` | `Profile.vue` | 无任何测试 |

### 1.3 缺失的验证维度

| 维度 | 现状 | 需要补充 |
|------|------|----------|
| **视觉回归** | ❌ 无 | 全部 22 页面截图基线对比 |
| **设计令牌验证** | ❌ 无 | CSS 变量值断言（`--primary`、`--ink` 等） |
| **响应式断点** | ❌ 无 | 1100px / 960px / 640px 三档布局验证 |
| **无障碍** | ❌ 无 | aria 属性、键盘导航、焦点可见性 |
| **侧边栏交互** | ❌ 无 | 折叠/展开、导航跳转、active 状态 |
| **顶栏交互** | ❌ 无 | 搜索框 `/` 快捷键、用户下拉菜单 |
| **旧色值残留** | ❌ 无 | 验证页面无旧色值（`#0369a1` 等） |

---

## 2. 测试计划总览

### 2.1 新增测试文件清单

| # | 文件名 | 类型 | 用例数 | 优先级 |
|---|--------|------|--------|--------|
| A | `test_visual_regression.spec.ts` | 视觉回归 | 22 | P0 |
| B | `test_design_tokens.spec.ts` | 设计令牌 | 8 | P0 |
| C | `test_layout_shell.spec.ts` | 布局框架 | 12 | P0 |
| D | `test_reset_password.spec.ts` | 功能验证 | 5 | P1 |
| E | `test_profile_page.spec.ts` | 功能验证 | 8 | P1 |
| F | `test_analytics_profile.spec.ts` | 功能验证 | 7 | P1 |
| G | `test_analytics_forecast.spec.ts` | 功能验证 | 7 | P1 |
| H | `test_industry_types.spec.ts` | 功能验证 | 5 | P1 |
| I | `test_database_management.spec.ts` | 功能验证 | 4 | P1 |
| J | `test_responsive.spec.ts` | 响应式 | 15 | P1 |
| K | `test_accessibility.spec.ts` | 无障碍 | 10 | P1 |
| L | `test_users_enhanced.spec.ts` | 功能增强 | 10 | P2 |
| M | `test_tags_enhanced.spec.ts` | 功能增强 | 8 | P2 |
| | **合计** | | **121** | |

### 2.2 需修复的现有测试文件

| 文件 | 问题 | 修复内容 |
|------|------|----------|
| `test_sync_task.spec.ts` | 选择器错误 | `input[name="username"]` → `input[field="username"]`；`waitForURL('/dashboard')` → `waitForURL('/')` |
| `test_core_pages_rendering.spec.ts` | 选择器过时 | `.stat-card` count 断言、heading text 更新 |
| `test_users.spec.ts` | 断言弱 | 移除 `if isVisible` 守卫，改为 `expect` 断言 |
| `test_tags.spec.ts` | 断言弱 | 同上 |
| `test_billing_workflow.spec.ts` | `waitForTimeout` | 替换为 web-first assertions |

---

## 3. 详细测试用例设计

### A. 视觉回归测试 (`test_visual_regression.spec.ts`)

**策略**: 每个页面截取全页截图，与基线对比。首次运行生成基线，后续运行对比。

```
describe('视觉回归测试')
  beforeEach: 登录 → 导航到目标页面 → 等待 networkidle

  A01: 登录页截图对比 (/login)
  A02: 首页截图对比 (/)
  A03: 客户列表截图对比 (/customers)
  A04: 客户详情截图对比 (/customers/:id) — 需 API 准备测试客户
  A05: 标签管理截图对比 (/tags)
  A06: 余额管理截图对比 (/billing/balances)
  A07: 计费规则截图对比 (/billing/pricing-rules)
  A08: 结算单截图对比 (/billing/invoices)
  A09: 消耗分析截图对比 (/analytics/consumption)
  A10: 回款分析截图对比 (/analytics/payment)
  A11: 健康度分析截图对比 (/analytics/health)
  A12: 画像分析截图对比 (/analytics/profile)
  A13: 预测回款截图对比 (/analytics/forecast)
  A14: 用户管理截图对比 (/users)
  A15: 角色管理截图对比 (/roles)
  A16: 同步日志截图对比 (/system/sync-logs)
  A17: 审计日志截图对比 (/system/audit-logs)
  A18: 行业类型截图对比 (/system/industry-types)
  A19: 数据清空截图对比 (/system/database-management)
  A20: 个人信息截图对比 (/profile)
  A21: 重置密码截图对比 (/reset-password?token=test)
  A22: 侧边栏折叠态截图对比 (/ → 折叠)
```

**截图配置**:
- `fullPage: true`
- `maxDiffPixelRatio: 0.1`（允许 10% 像素差异，容忍字体渲染差异）
- 动态数据区域使用 `mask` 遮罩（表格内容、图表 canvas）

---

### B. 设计令牌验证 (`test_design_tokens.spec.ts`)

**策略**: 通过 `page.evaluate()` 读取 `getComputedStyle` 验证 CSS 变量值。

```
describe('设计令牌验证')
  beforeEach: 登录 → 导航到首页

  B01: :root 变量值正确
    - --primary = #1D4ED8
    - --ink = #0F172A
    - --muted = #475569
    - --bg = #F6F8FB
    - --panel = #FFFFFF
    - --line = #DBE3EF
    - --radius = 18px
    - --font-stack 包含 'Inter'

  B02: Arco 主题覆盖正确
    - --primary-6 = #1D4ED8（Arco 主色变量）
    - 按钮 primary 背景为渐变 linear-gradient(135deg, #1D4ED8, #2563EB)

  B03: 侧边栏品牌标识样式
    - .mark 背景为 linear-gradient(135deg, #3B82F6, #06B6D4)
    - .mark border-radius = 13px
    - .mark 文字内容 = "VK"

  B04: 侧边栏背景样式
    - .side 背景包含 radial-gradient 和 linear-gradient
    - .side 文字颜色 = rgb(203, 213, 225) (#CBD5E1)

  B05: 顶栏毛玻璃效果
    - .top backdrop-filter 包含 blur(14px)
    - .top 背景为 rgba(246, 248, 251, .86)

  B06: 搜索框样式
    - .search border-radius = 14px
    - .search border-color = var(--line)

  B07: 页面无旧色值残留
    - 遍历所有元素，检查 computed color/background 不包含 #0369a1, #0284c7, #0f172a
    - 检查所有 <style> 和内联样式不含旧色值

  B08: ECharts 配色验证
    - 导航到 /analytics/consumption
    - 读取 canvas 上下文，验证图表颜色不包含旧色值
```

---

### C. 布局框架测试 (`test_layout_shell.spec.ts`)

**策略**: 验证 Dashboard 布局、侧边栏、顶栏的核心交互。

```
describe('布局框架')

  describe('Dashboard Grid 布局')
    C01: .shell 使用 grid 布局
      - grid-template-columns = '252px 1fr'
    C02: 折叠态 .shell.collapsed grid-template-columns = '72px 1fr'
    C03: 内容区 max-width = 1440px
    C04: 内容区 padding = 22px 24px 44px

  describe('侧边栏交互')
    C05: 点击折叠按钮 → .shell 添加 collapsed 类
    C06: 折叠后 localStorage 'prototype-sidebar-collapsed' = 'true'
    C07: 刷新页面后折叠状态持久化
    C08: 展开后 localStorage 值更新
    C09: 导航菜单点击跳转正确（/customers, /billing/balances, /analytics/consumption 等）
    C10: 子菜单展开/折叠（结算管理、客户分析）
    C11: active 菜单项 aria-current="page" 属性正确

  describe('顶栏交互')
    C12: 搜索框 role="search" + aria-label="全局搜索"
    C13: 按 '/' 键聚焦搜索框（输入框不在 focus 时）
    C14: 搜索框 Enter 触发搜索提示
```

---

### D. 重置密码页面 (`test_reset_password.spec.ts`)

```
describe('重置密码页面')
  D01: 无 token 访问显示"重置链接无效"
    - goto /reset-password (无 token 参数)
    - 验证错误提示可见
  D02: 带 token 访问显示重置表单
    - goto /reset-password?token=test-token
    - 验证新密码/确认密码输入框可见
  D03: 密码不一致校验
    - 填入新密码 "abc123"，确认密码 "xyz789"
    - 提交 → 验证"两次输入的密码不一致"提示
  D04: 密码长度校验
    - 填入新密码 "abc"（< 6 位）
    - 验证"密码长度不能少于 6 位"提示
  D05: 页面视觉规范
    - 卡片 border-radius = 18px
    - 按钮使用主色渐变
```

---

### E. 个人信息页面 (`test_profile_page.spec.ts`)

```
describe('个人信息页面')
  beforeEach: 登录 → goto /profile

  E01: 页面加载 — PageHeader 显示 eyebrow "个人" + 标题 "个人信息"
  E02: 左右分栏布局 — grid-template-columns = '1fr 1fr'
  E03: 头像区域
    - 头像 80×80px, border-radius = 50%
    - 默认头像背景 #DBEAFE, 文字颜色 var(--primary)
    - 显示用户名/邮箱
  E04: 基本信息字段
    - 用户名（disabled）、真实姓名、邮箱、手机号、最后登录时间
  E05: 保存功能
    - 修改邮箱 → 点击保存 → 验证成功提示
  E06: 修改密码弹窗
    - 点击"修改密码" → 弹窗显示
    - 填入当前密码/新密码/确认密码 → 提交
  E07: 头像上传校验
    - 上传非图片文件 → 验证"仅支持 JPG/PNG"提示
    - 上传 > 2MB 文件 → 验证"不能超过 2MB"提示
  E08: 取消按钮 → router.back()
```

---

### F. 画像分析页面 (`test_analytics_profile.spec.ts`)

```
describe('画像分析页面')
  beforeEach: 登录 → goto /analytics/profile

  F01: PageHeader — eyebrow "运营分析" + 标题 "画像分析"
  F02: 4 KPI 卡片
    - 客户总数 / 行业覆盖 / 房产客户+占比 / 数据完整率
  F03: 强制刷新按钮 → 成功提示
  F04: 行业分布饼图渲染 — canvas 可见且非空白
  F05: 规模等级柱图渲染
    - 无有效数据时显示 "-"
  F06: 消费等级环形图渲染
  F07: 房产客户独立行业分布饼图（橙色系配色）
```

---

### G. 预测回款页面 (`test_analytics_forecast.spec.ts`)

```
describe('预测回款页面')
  beforeEach: 登录 → goto /analytics/forecast

  G01: PageHeader — eyebrow "运营分析" + 标题 "预测回款"
  G02: 年份选择器 + 月份选择器（全年/1-12月）
  G03: 4 KPI 卡片
    - 预测总额 / 已确认+完成率 / 待确认 / 预测客户数
  G04: 月份切换 → 数据刷新
  G05: 月度预测图表渲染（柱图+折线）
  G06: 预测明细表
    - 金额列排序功能
    - 分页功能
    - 点击"查看"跳转客户详情
  G07: 年份切换 → 数据刷新
```

---

### H. 行业类型页面 (`test_industry_types.spec.ts`)

```
describe('行业类型页面')
  beforeEach: 登录 → goto /system/industry-types

  H01: PageHeader 显示
  H02: 行业列表表格渲染
  H03: 创建行业类型
    - 点击新建 → 弹窗
    - 填入名称 + 排序号 → 提交 → 验证成功提示 + 列表更新
  H04: 编辑行业类型
    - 点击编辑 → 弹窗预填数据 → 修改 → 提交 → 验证更新
  H05: 删除行业类型
    - 点击删除 → 确认弹窗 → 确认 → 验证列表更新
```

---

### I. 数据清空页面 (`test_database_management.spec.ts`)

```
describe('数据清空页面')
  beforeEach: 登录 → goto /system/database-management

  I01: PageHeader 显示
  I02: 权限校验 — 有 system:database_clear 权限才可访问
  I03: 清空确认弹窗
    - 点击清空 → 确认弹窗显示
    - 取消 → 弹窗关闭，无操作
  I04: 清空结果展示
    - 确认清空 → 结果区域显示成功/失败信息
```

---

### J. 响应式断点测试 (`test_responsive.spec.ts`)

**策略**: 使用 `page.setViewportSize` 模拟不同屏幕宽度。

```
describe('响应式断点测试')

  describe('≤ 1100px 断点')
    beforeEach: setViewportSize(1100, 800) + 登录

    J01: 侧边栏切为 fixed 定位（position: fixed）
    J02: 侧边栏默认隐藏（translateX(-100%)）
    J03: 点击移动端菜单按钮 → 侧边栏滑出
    J04: .grid-4/.grid-3/.grid-2 切为 1fr（单列）
    J05: .kpi-strip 切为 repeat(2, 1fr)
    J06: .desktop-only 元素隐藏
    J07: 移动端遮罩层显示

  describe('≤ 960px 断点')
    beforeEach: setViewportSize(960, 800)

    J08: 登录页切单列布局（grid-template-columns: 1fr）
    J09: 登录页品牌区+表单区垂直堆叠
    J10: 登录页第 3+ 特性项隐藏

  describe('≤ 640px 断点')
    beforeEach: setViewportSize(640, 800)

    J11: 登录页全屏无圆角（border-radius: 0）
    J12: 页面 padding 缩小至 16px
    J13: 搜索框换行全宽
    J14: .kpi-strip 切为单列
    J15: .nav-hint 元素隐藏
```

---

### K. 无障碍测试 (`test_accessibility.spec.ts`)

```
describe('无障碍测试')

  describe('侧边栏无障碍')
    K01: 折叠按钮 aria-label 动态更新
      - 展开态: aria-label="收起侧边栏", aria-expanded="true"
      - 折叠态: aria-label="展开侧边栏", aria-expanded="false"
    K02: 导航 nav aria-label="主导航"
    K03: active 菜单项 aria-current="page"

  describe('顶栏无障碍')
    K04: 搜索框 role="search" + aria-label="全局搜索"
    K05: SVG 图标 aria-hidden="true"

  describe('键盘导航')
    K06: Tab 键可以在侧边栏菜单项之间循环
    K07: '/' 键聚焦搜索框
    K08: Enter 键在搜索框中触发搜索

  describe('焦点可见性')
    K09: 所有可交互元素 focus-visible 有 outline
      - 检查 *:focus-visible 的 outline 样式不为 none
    K10: 色彩对比度
      - 正文文字与背景对比度 ≥ 4.5:1
      - 大文字 ≥ 3:1
```

---

### L. 用户管理增强测试 (`test_users_enhanced.spec.ts`)

**替换现有浅层 `test_users.spec.ts`**

```
describe('用户管理增强测试')
  beforeEach: 登录 → goto /users

  L01: PageHeader — eyebrow "系统管理" + 标题 "用户管理"
  L02: 搜索功能
    - 输入关键词 → 表格过滤
    - 清空搜索 → 恢复全部
  L03: 创建用户
    - 点击新建 → 弹窗
    - 填入用户名/密码/邮箱/真实姓名/角色
    - 提交 → 成功提示 + 列表更新
  L04: 编辑用户
    - 用户名不可编辑（disabled）
    - 状态开关切换
    - 角色多选
  L05: 重置密码弹窗
    - 新密码 + 确认密码 + 一致性校验
  L06: 删除用户 — 确认弹窗
  L07: 角色显示 — 多角色 tooltip
  L08: 邮箱格式校验
  L09: 分页 — 页码切换 + 每页条数
  L10: 状态标签样式 — .status-badge .success/.danger
```

---

### M. 标签管理增强测试 (`test_tags_enhanced.spec.ts`)

**替换现有浅层 `test_tags.spec.ts`**

```
describe('标签管理增强测试')
  beforeEach: 登录 → goto /tags

  M01: PageHeader — eyebrow "系统管理" + 标题 "标签管理"
  M02: 客户标签 / 画像标签 Tab 切换
  M03: 新建标签
    - 名称 + 类型 + 分类
    - 提交 → 成功提示 + 列表更新
  M04: 编辑标签 — 点击标签 → 编辑弹窗
  M05: 删除标签 — 关闭标签 → 确认删除
  M06: 分页功能
  M07: 标签云展示 — .tag 药丸样式（border-radius: 999px）
  M08: Tab 药丸样式 — border-radius: 999px
```

---

## 4. 现有测试修复清单

### 4.1 `test_sync_task.spec.ts` — 选择器修复

| 行号 | 当前 | 修复为 |
|------|------|--------|
| 16 | `input[name="username"]` | `input[field="username"], input[type="text"]` |
| 17 | `input[name="password"]` | `input[field="password"], input[type="password"]` |
| 19 | `waitForURL('/dashboard')` | `waitForURL('/')` |

### 4.2 `test_core_pages_rendering.spec.ts` — 选择器更新

| 测试 | 当前问题 | 修复方案 |
|------|----------|----------|
| 仪表盘布局 | `.stat-card` count=4 可能不匹配 | 改为 `toHaveCount` 最小值或更新选择器 |
| 登录页 | `test.skip` | 修复选择器，取消 skip |
| 各页标题 | `getByRole('heading', {level: 1})` text | 更新为重构后的标题文本 |

### 4.3 `test_billing_workflow.spec.ts` — 等待策略

| 当前 | 修复为 |
|------|--------|
| `waitForTimeout(1500)` | `waitForLoadState('networkidle')` 或 `waitForSelector` |
| `if (await x.isVisible())` 守卫 | `await expect(x).toBeVisible()` 断言 |

---

## 5. 执行策略

### 5.1 前置条件

```bash
# 1. 后端服务运行
cd backend && make dev  # http://localhost:8000

# 2. 前端开发服务运行
cd frontend && npm run dev  # http://localhost:5173

# 3. Redis 运行
redis-server --daemonize yes

# 4. 测试账号存在
# admin / admin123 (超级管理员)
```

### 5.2 执行顺序

| 阶段 | 内容 | 命令 |
|------|------|------|
| 1 | 修复现有测试 | `npx playwright test test_sync_task.spec.ts test_core_pages_rendering.spec.ts` |
| 2 | 视觉回归基线生成 | `npx playwright test test_visual_regression.spec.ts --update-snapshots` |
| 3 | 设计令牌 + 布局框架 | `npx playwright test test_design_tokens.spec.ts test_layout_shell.spec.ts` |
| 4 | 功能验证（新页面） | `npx playwright test test_reset_password.spec.ts test_profile_page.spec.ts test_analytics_profile.spec.ts test_analytics_forecast.spec.ts test_industry_types.spec.ts test_database_management.spec.ts` |
| 5 | 功能增强（替换浅层测试） | `npx playwright test test_users_enhanced.spec.ts test_tags_enhanced.spec.ts` |
| 6 | 响应式 + 无障碍 | `npx playwright test test_responsive.spec.ts test_accessibility.spec.ts` |
| 7 | 全量回归 | `npx playwright test` |

### 5.3 截图基线管理

- 基线存储路径: `tests/e2e/visual-baselines/`
- 首次运行: `npx playwright test test_visual_regression.spec.ts --update-snapshots`
- 日常对比: `npx playwright test test_visual_regression.spec.ts`
- 更新基线（设计变更后）: 加 `--update-snapshots` 参数

### 5.4 CI 集成

```yaml
# .github/workflows/e2e-tests.yml
- name: Run E2E tests
  run: |
    cd frontend
    npx playwright install --with-deps chromium
    npx playwright test --project=chromium --reporter=list
- name: Upload artifacts
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: frontend/tests/e2e/playwright-report/
```

---

## 6. 验收标准

| 维度 | 标准 | 验证方法 |
|------|------|----------|
| 功能完整性 | 22 页面全部有 E2E 测试覆盖 | `npx playwright test --list` 统计 |
| 视觉一致性 | 截图对比通过率 ≥ 95% | `test_visual_regression.spec.ts` |
| 设计令牌 | CSS 变量值 100% 匹配规范 | `test_design_tokens.spec.ts` |
| 响应式 | 3 个断点布局正确 | `test_responsive.spec.ts` |
| 无障碍 | aria 属性正确、键盘可用、焦点可见 | `test_accessibility.spec.ts` |
| 无旧色值 | 页面中 0 个旧色值残留 | `test_design_tokens.spec.ts` B07 |
| 全量通过 | `npx playwright test` 0 failures | 最终回归 |
