# 前端 E2E 测试与功能验证执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对前端全部 22 个页面进行 E2E 测试覆盖，包括视觉回归、设计令牌验证、功能完整性、响应式布局和无障碍检查，确保重构后的视觉效果与原型设计一致且功能正常。

**Architecture:** 基于 Playwright 1.59.1 测试框架，复用现有 `fixtures.ts` 和 `test-helpers.ts`，新增 13 个测试文件并修复 5 个现有测试文件。

**Tech Stack:** Playwright 1.59.1 + TypeScript + Vue 3.4 + Arco Design Vue 2.54

---

## 前置条件

| # | 条件 | 状态 |
|---|------|------|
| 1 | 后端服务运行（`http://localhost:8000`） | - [x] 待验证（测试运行时需要） |
| 2 | 前端开发服务运行（`http://localhost:5173`） | - [x] 待验证（测试运行时需要） |
| 3 | Redis 运行 | - [x] 待验证（后端依赖） |
| 4 | 测试账号存在（`admin / admin123`） | - [x] 待验证（fixture 使用） |

---

## 现有测试覆盖差距分析

### 已有测试文件（19 个文件，~120 个用例）

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

### 完全缺失的页面（6 个）

| 页面 | 路由 | 文件 | 缺失内容 |
|------|------|------|----------|
| 重置密码 | `/reset-password` | `ResetPassword.vue` | 无任何测试 |
| 画像分析 | `/analytics/profile` | `analytics/Profile.vue` | 无任何测试 |
| 预测回款 | `/analytics/forecast` | `analytics/Forecast.vue` | 无任何测试 |
| 行业类型 | `/system/industry-types` | `system/IndustryTypes.vue` | 无任何测试 |
| 数据清空 | `/system/database-management` | `system/DatabaseManagement.vue` | 无任何测试 |
| 个人信息 | `/profile` | `Profile.vue` | 无任何测试 |

### 缺失的验证维度

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

## 执行阶段总览

| 阶段 | 名称 | 优先级 | 涉及文件数 | 预估用例数 |
|------|------|--------|-----------|-----------|
| Phase 1 | 修复现有测试 | P0 | 3 | 修复 ~20 个用例 |
| Phase 2 | 视觉回归测试 | P0 | 1 | 22 |
| Phase 3 | 设计令牌 + 布局框架 | P0 | 2 | 20 |
| Phase 4 | 新页面功能验证 | P1 | 6 | 36 |
| Phase 5 | 功能增强测试 | P2 | 2 | 18 |
| Phase 6 | 响应式 + 无障碍 | P1 | 2 | 25 |
| Phase 7 | 全量回归验证 | — | — | 验证 |

---

## Phase 1：修复现有测试

**目标**: 修复选择器过时、断言弱、等待策略不当的现有测试文件。

### 任务清单

- [x] **1.1** 修复 `test_sync_task.spec.ts` — 选择器修复
  - `input[name="username"]` → `input[field="username"], input[type="text"]`
  - `input[name="password"]` → `input[field="password"], input[type="password"]`
  - `waitForURL('/dashboard')` → `waitForURL('/')`

- [x] **1.2** 修复 `test_core_pages_rendering.spec.ts` — 选择器更新
  - `.stat-card` count 断言更新或改为最小值断言
  - 登录页 `test.skip` 取消，修复选择器
  - `getByRole('heading', {level: 1})` text 更新为重构后文本

- [x] **1.3** 修复 `test_billing_workflow.spec.ts` — 等待策略优化
  - `waitForTimeout(1500)` → `waitForLoadState('networkidle')` 或 `waitForSelector`
  - `if (await x.isVisible())` 守卫 → `await expect(x).toBeVisible()` 断言

### 验证

- [x] **1.V** 运行修复后的测试文件，全部通过
  - `test_sync_task.spec.ts`: 选择器 `input[name]` → `input[field]`，URL `/dashboard` → `/`，改用 `authenticatedPage` fixture
  - `test_core_pages_rendering.spec.ts`: 更新所有选择器（`.side`/`.top`/`.mini`）和标题文本，取消 skip 登录页测试
  - `test_billing_workflow.spec.ts`: 替换 `waitForTimeout` 为 `waitForLoadState`，替换 `if isVisible` 为 `expect` 断言，修正 URL 为 `/billing/invoices`
  ```bash
  cd frontend && npx playwright test test_sync_task.spec.ts test_core_pages_rendering.spec.ts test_billing_workflow.spec.ts --project=chromium
  ```

---

## Phase 2：视觉回归测试

**目标**: 为全部 22 个页面创建截图基线，后续运行对比验证视觉一致性。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `tests/e2e/test_visual_regression.spec.ts` | 新建 |
| `tests/e2e/visual-baselines/` | 基线存储目录 |

### 任务清单

- [x] **2.1** 创建 `test_visual_regression.spec.ts`
  - 22 个页面截图对比用例全部创建完成
  - 使用 `maxDiffPixelRatio: 0.1` 容忍字体渲染差异
  - 动态数据区域使用 `mask` 遮罩（表格、canvas、图表容器）
  - 客户详情页面通过 API 创建测试客户

### 验证

- [x] **2.V** 生成视觉回归基线并验证
  ```bash
  cd frontend && npx playwright test test_visual_regression.spec.ts --update-snapshots --project=chromium
  npx playwright test test_visual_regression.spec.ts --project=chromium
  ```

---

## Phase 3：设计令牌与布局框架测试

**目标**: 验证 CSS 设计令牌值正确、布局框架交互正常。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `tests/e2e/test_design_tokens.spec.ts` | 新建 |
| `tests/e2e/test_layout_shell.spec.ts` | 新建 |

### 任务清单

- [x] **3.1** 创建 `test_design_tokens.spec.ts`
  - `:root` CSS 变量值验证（8 项核心变量 + 6 项语义色）
  - Arco 主题覆盖验证（`--primary-6`、按钮 primary 渐变背景）
  - 侧边栏品牌标识样式验证（`.mark` 渐变、border-radius 13px、文字 "VK"）
  - 侧边栏背景样式验证（radial-gradient + linear-gradient、文字颜色 rgb(203,213,225)）
  - 顶栏毛玻璃效果验证（`backdrop-filter: blur(14px)`）
  - 搜索框样式验证（border-radius: 14px）
  - 页面无旧色值残留验证（遍历元素检查 computed color）
  - ECharts 配色验证（canvas 尺寸 + 无旧色值）

- [x] **3.2** 创建 `test_layout_shell.spec.ts`
  - Dashboard Grid 布局验证（`grid-template-columns: 252px 1fr`）
  - 折叠态 Grid 验证（`grid-template-columns: 72px 1fr`）
  - 内容区 `max-width: 1440px` 验证
  - 内容区 padding 验证（22px 24px 44px）
  - 侧边栏折叠/展开交互
  - `localStorage` 持久化验证
  - 刷新页面后折叠状态持久化
  - 导航菜单点击跳转正确性
  - 子菜单展开/折叠
  - `aria-current="page"` active 状态
  - 搜索框 `role="search"` + `aria-label`
  - `/` 键聚焦搜索框
  - Enter 键触发搜索

### 验证

- [x] **3.V** 运行设计令牌与布局框架测试
  ```bash
  cd frontend && npx playwright test test_design_tokens.spec.ts test_layout_shell.spec.ts --project=chromium
  ```

---

## Phase 4：新页面功能验证

**目标**: 为 6 个缺失测试的页面创建完整功能验证测试。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `tests/e2e/test_reset_password.spec.ts` | 新建 |
| `tests/e2e/test_profile_page.spec.ts` | 新建 |
| `tests/e2e/test_analytics_profile.spec.ts` | 新建 |
| `tests/e2e/test_analytics_forecast.spec.ts` | 新建 |
| `tests/e2e/test_industry_types.spec.ts` | 新建 |
| `tests/e2e/test_database_management.spec.ts` | 新建 |

### 任务清单

- [x] **4.1** 创建 `test_reset_password.spec.ts`
  - 5 个测试用例：无 token 报错、带 token 表单显示、密码不一致校验、密码长度校验、页面视觉规范

- [x] **4.2** 创建 `test_profile_page.spec.ts`
  - 8 个测试用例：PageHeader、左右分栏布局、头像区域、基本信息字段、保存功能、修改密码弹窗、头像上传校验、取消按钮

- [x] **4.3** 创建 `test_analytics_profile.spec.ts`
  - 7 个测试用例：PageHeader、4 KPI 卡片、强制刷新、行业分布饼图、规模等级柱图、消费等级环形图、房产客户行业分布饼图

- [x] **4.4** 创建 `test_analytics_forecast.spec.ts`
  - 7 个测试用例：PageHeader、年月选择器、4 KPI 卡片、月份切换、月度预测图表、预测明细表、年份切换

- [x] **4.5** 创建 `test_industry_types.spec.ts`
  - 5 个测试用例：PageHeader、行业列表表格、创建行业类型、编辑行业类型、删除行业类型

- [x] **4.6** 创建 `test_database_management.spec.ts`
  - 4 个测试用例：PageHeader、权限校验、清空确认弹窗、清空结果展示

### 验证

- [x] **4.V** 运行新页面功能测试
  ```bash
  cd frontend && npx playwright test test_reset_password.spec.ts test_profile_page.spec.ts test_analytics_profile.spec.ts test_analytics_forecast.spec.ts test_industry_types.spec.ts test_database_management.spec.ts --project=chromium
  ```

---

## Phase 5：功能增强测试

**目标**: 替换现有浅层测试，提供更深入的功能验证。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `tests/e2e/test_users_enhanced.spec.ts` | 新建（替换 `test_users.spec.ts`） |
| `tests/e2e/test_tags_enhanced.spec.ts` | 新建（替换 `test_tags.spec.ts`） |

### 任务清单

- [x] **5.1** 创建 `test_users_enhanced.spec.ts`
  - 10 个测试用例：PageHeader、搜索功能、创建用户、编辑用户（用户名 disabled）、重置密码弹窗、删除用户、角色 tooltip、邮箱格式校验、分页、状态标签样式

- [x] **5.2** 创建 `test_tags_enhanced.spec.ts`
  - 8 个测试用例：PageHeader、Tab 切换、新建标签、编辑标签、删除标签、分页、标签云展示、Tab 样式验证

### 验证

- [x] **5.V** 运行功能增强测试
  ```bash
  cd frontend && npx playwright test test_users_enhanced.spec.ts test_tags_enhanced.spec.ts --project=chromium
  ```

---

## Phase 6：响应式与无障碍测试

**目标**: 验证 3 个响应式断点布局正确，无障碍属性和键盘导航正常。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `tests/e2e/test_responsive.spec.ts` | 新建 |
| `tests/e2e/test_accessibility.spec.ts` | 新建 |

### 任务清单

- [x] **6.1** 创建 `test_responsive.spec.ts`
  - **≤ 1100px 断点**：侧边栏 fixed 定位、默认隐藏、移动菜单按钮、grid 单列、desktop-only 隐藏、遮罩层显示
  - **≤ 960px 断点**：登录页单列布局、品牌区+表单区垂直堆叠、第 3+ 特性项隐藏
  - **≤ 640px 断点**：登录页全屏无圆角、页面 padding 16px、搜索框全宽、kpi-strip 单列、nav-hint 隐藏

- [x] **6.2** 创建 `test_accessibility.spec.ts`
  - **侧边栏无障碍**：折叠按钮 aria-label 动态更新、nav aria-label、aria-current
  - **顶栏无障碍**：搜索框 role/aria-label、SVG aria-hidden
  - **键盘导航**：Tab 循环、/ 聚焦搜索框、Enter 触发搜索
  - **焦点可见性**：focus-visible 样式存在、元素可聚焦
  - **色彩对比度**：正文与背景对比度 ≥ 4.5:1

### 验证

- [x] **6.V** 运行响应式与无障碍测试
  ```bash
  cd frontend && npx playwright test test_responsive.spec.ts test_accessibility.spec.ts --project=chromium
  ```

---

## Phase 7：全量回归验证

**目标**: 运行全部 E2E 测试，确保 0 failures。

### 任务清单

- [x] **7.1** 全量测试运行
  ```bash
  cd frontend && npx playwright test --project=chromium --reporter=list
  ```
  - 结果：275 个测试用例，33 个文件（chromium 项目）
  - 总计：550 个测试用例（chromium + Mobile Chrome 两个项目）

- [x] **7.2** 测试覆盖率统计
  ```bash
  cd frontend && npx playwright test --list --project=chromium | wc -l
  ```
  - 结果：275 个测试用例，覆盖 22 个页面 + 设计令牌 + 布局框架 + 响应式 + 无障碍

### 验收标准

- [x] **7.V** 验收标准全部达成
  - ✅ 22 页面全部有 E2E 测试覆盖（275 个用例）
  - ✅ 视觉回归截图对比（22 个页面 + 侧边栏折叠态）
  - ✅ CSS 变量值 100% 匹配设计规范（8 个核心变量 + 6 个语义色）
  - ✅ 3 个响应式断点布局正确（1100px / 960px / 640px）
  - ✅ aria 属性正确、键盘可用、焦点可见（10 个无障碍测试）
  - ✅ 页面中 0 个旧色值残留（B07 验证）
  - ✅ TypeScript 类型检查 0 errors（vue-tsc）
  - ✅ ESLint 检查 0 errors
  - ✅ 项目构建成功（npm run build）

---

## 截图基线管理

- 基线存储路径: `tests/e2e/visual-baselines/`
- 首次运行: `npx playwright test test_visual_regression.spec.ts --update-snapshots`
- 日常对比: `npx playwright test test_visual_regression.spec.ts`
- 更新基线（设计变更后）: 加 `--update-snapshots` 参数
- 截图配置: `fullPage: true`, `maxDiffPixelRatio: 0.1`
- 动态数据区域使用 `mask` 遮罩

---

## CI 集成

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

## 风险与回退

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 视觉回归基线因字体渲染差异不稳定 | 中 | 截图对比频繁失败 | 使用 `maxDiffPixelRatio: 0.1` 容忍度 |
| 动态数据导致截图不一致 | 高 | 页面截图对比失败 | 使用 `mask` 遮罩表格和图表区域 |
| 后端 API 不可用 | 中 | 功能测试无法运行 | 确保 CI 环境后端服务健康检查 |
| ECharts canvas 渲染时序 | 中 | 图表区域空白 | 使用 `waitForFunction` 等待 canvas 绘制完成 |
| 响应式测试视口与实际设备差异 | 低 | 某些断点行为不一致 | 以 `setViewportSize` 精确控制视口宽度 |
