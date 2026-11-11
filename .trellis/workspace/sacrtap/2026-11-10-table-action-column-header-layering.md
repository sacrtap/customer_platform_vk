# 列表表格「操作列」与 Header 层级错误：修复与验收记录

日期：2026-11-10
分支：`main`（工作区干净起点）

## 1. 问题

多个页面列表表格的操作列（`fixed: right`）与吸顶表头在滚动时渲染到全局 Header 之上，表现为操作按钮/表头压住顶部导航。

用户列出的页面：客户管理、余额管理、计费规则、包年套餐、结算单管理、VR编辑费用结算、健康度分析、预测消费、用户管理、角色权限、行业类型、合作状态、ERP系统、余额白名单、API-Key、数据备份。

## 2. 根因

`.arco-table` 内部用 `position: sticky` 实现吸顶表头与固定列，并给表头/固定列设置 `z-index`（表头 5、固定列 10）。这些 `z-index` 属于**根层叠上下文**，因为 `.arco-table` 自身没有建立层叠上下文。

全局 Header（`AppHeader`）的 `z-index` 低于 10（实测 5），于是表格内部的 sticky 元素在滚动进入 Header 区域时绘制在其上方。

## 3. 修复

`frontend/src/styles/arco-theme.css`：

```css
.arco-table {
  isolation: isolate;
}
```

`isolation: isolate` 让每个表格成为独立层叠上下文，内部 `z-index` 只在表格内部比较，不再与全局 Header 竞争。相比逐个调高 Header `z-index`，该方案不引入新的全局数值竞赛，且对 Teleport 到 `body` 的浮层（Modal/Drawer/Select/Dropdown/Tooltip）无影响——浮层不在表格子树内，不受其层叠上下文约束。

## 4. 回归用例

`frontend/tests/e2e/test_visual_regression.spec.ts` 新增 `A23: 操作列滚动时不得覆盖全局Header`：

- 数据备份列表用浏览器内 fixture 补 20 行（不写库）。
- 视口高度压到 483px 以强制出现滚动与吸顶。
- 滚动到表格中部后，用 `elementFromPoint` 判定表头与操作列交界处的最上层元素必须是 Header。
- 额外打开「列设置」Modal，判定其同样位于最上层（验证 `isolation` 未压住 Teleport 浮层）。

## 5. 逐页验收矩阵

临时脚本（验收后已删除）对 17 张表格逐页执行：

- 表头/操作列与 Header 交界处 `elementFromPoint` 命中判定；
- 计算样式：表格 `isolation`、固定列 `z-index`、Header `z-index`；
- 横向滚动前后固定列位置漂移量。

环境：本地前后端（127.0.0.1:5173 / 8000），admin 登录态，视口 1440×483，Chromium。

本地 dev 库中客户与预测消费无数据，按项目真实类型定义构造**仅浏览器内** fixture（route 拦截，不写库），使每张表都有真实数据行。

| # | 页面 | 数据行 | 表格 isolation | 固定列 z | Header z | 表头交界命中 | 操作列交界命中 | 横向固定列 |
|---|---|---|---|---|---|---|---|---|
| 1 | 客户管理 `/customers` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 2 | 余额管理 `/billing/balances` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 3 | 计费规则 `/billing/pricing-rules` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 4 | 包年套餐 `/billing/package-plans` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 5 | 结算单管理 `/billing/invoices` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 6 | VR编辑费用结算 `/billing/vr-settlements` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 7 | 健康度分析 `/analytics/health`（表 1） | 10 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 8 | 健康度分析 `/analytics/health`（表 2） | 10 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 9 | 预测消费 `/analytics/forecast` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 10 | 用户管理 `/users` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |
| 11 | 角色权限 `/roles` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 12 | 行业类型 `/system/industry-types` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 13 | 合作状态 `/system/cooperation-statuses` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 14 | ERP系统 `/system/erp-systems` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 15 | 余额白名单 `/system/balance-whitelist` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 16 | API-Key `/system/api-keys` | 20 | isolate | 10 | 5 | ✅ | ✅ | 无横向溢出 |
| 17 | 数据备份 `/system/backup` | 20 | isolate | 10 | 5 | ✅ | ✅ | 稳定(0,0,0) |

17/17 通过。

## 6. 浮层回归

表格内触发的浮层逐项打开（只打开、不提交、随后取消/关闭），判定浮层中心点 `elementFromPoint` 命中浮层自身或其子树：

| 页面 | 入口 | 浮层 | 最上层命中 | 关闭成功 |
|---|---|---|---|---|
| 客户管理 | 行内「详情」 | `.preview-drawer`（自定义右侧抽屉） | ✅ | ✅ |
| 余额管理 | 行内「记录」 | Arco Modal（充值记录） | ✅ | ✅ |
| 结算单管理 | 行内「提交」 | Arco Modal（提交结算单） | ✅ | ✅ |
| 用户管理 | 行内「编辑」 | Arco Modal（编辑用户） | ✅ | ✅ |
| 角色权限 | 行内「权限配置」 | Arco Modal（权限配置） | ✅ | ✅ |

5/5 通过。加上 A23 覆盖的「列设置」Modal（Teleport 到 `body`），`isolation` 未压住任何浮层。

验证过程中的一个实现细节：Arco 会把已销毁的 Modal 节点保留为 `display: none`，用 `.arco-modal` 直接 `.first()` 会命中隐藏节点导致误判，必须用 `:visible` 过滤。

## 7. 验证命令

```bash
cd frontend
npx playwright test tests/e2e/test_visual_regression.spec.ts --project=chromium \
  --grep "A23" --workers=1 --retries=0 --reporter=list
npx tsc -b --noEmit
npm run lint
```

## 8. 限制与说明

- 逐页矩阵与浮层验证使用临时 Playwright 脚本，验收后删除，不进入仓库；长期防回归由 A23 承担（它覆盖固定列、吸顶表头与 Teleport 浮层三类风险）。
- 本地 dev 库客户/预测数据为空，矩阵中相应页使用浏览器内 fixture，未修改任何数据库数据。
