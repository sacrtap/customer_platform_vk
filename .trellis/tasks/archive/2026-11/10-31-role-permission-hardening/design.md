# 角色权限页面权限配置排查与加固 — Design

## 权限体系三层结构

```
seed.py ALL_PERMISSIONS（单一事实源）
   → DB permissions 表
      → 后端 require_permission("module:action") 强制（middleware/auth.py:214）
      → 前端 can()/hasPermission/路由 meta.requiresPermission 门控
      → tests/_test_data.py PERMISSION_ROWS（测试夹具 ⊆ seed，已有 consistency 测试守护）
```

本任务在「后端强制」与「前端门控」两层补齐，并新增第三层守护（drift 测试）防三处漂移。

## 核实结论与 PLAN 偏差修正（已逐项读码验证，2026-10-31）

| # | PLAN 描述 | 磁盘事实 | 处理 |
|---|-----------|---------|------|
| 1 | seed ALL_PERMISSIONS 67 项 | 实际 66 项（7+18+4+6+7+7+2+2+3+3+1+3+2+1+1） | 以磁盘为准，追加 sync_tasks:manage 后 67 项 |
| 2 | 缺口 9：「`analytics:export` 前端无入口（后端 `/analytics/health/export` 存在）」 | `/health/export`(analytics.py:1372-1374) **已有** `@require_permission("analytics:export")`；`/consumption/accuracy` 与 `/consumption/price-config` PUT 已有 `analytics:forecast_edit` | Phase 2 仅加前端入口，后端无需补码；PLAN 26 端点列表不含这三者，正确 |
| 3 | 步骤 13：Consumption.vue「数据同步」按钮（9 行）加门 | 实际有**两个**调用点：10 行主按钮 + 26 行「手动同步」mini 按钮，均调 `handleSyncButtonClick` | 两个都加 `v-if="can('sync_tasks:manage')"` |
| 4 | 步骤 17：InvoiceLogs 三处对齐 | AppSidebar.vue 中**无** InvoiceLogs/「结算单日志」按钮（系统工具组只有同步日志/审计日志）；useAppLayout.ts navSections 无任何消费者（仅内部 return） | 实际改两处：router/index.ts:189 meta + useAppLayout.ts:136 navSections 数据。navSections 虽无当前消费者，作为数据副本仍同步防未来漂移 |

已确认与 PLAN 一致的关键事实：
- analytics.py 36 路由装饰器栈与 PLAN 列表逐条吻合（26 纯 auth_required GET + sync + 3 上下文端点 + dashboard×3 + priority-customers 白名单 + accuracy/price-config PUT/health/export 已有码）。
- sync_tasks.py 8 端点、sync_logs.py 2 端点全无权限码。
- customers.py：import-template(1336-1338)、summary(1644)/related(1700)/balance-forecast(1750)/follow-up(1804) 均纯 auth_required。
- billing 4 个 import-template：imports.py:277、invoices.py:2213、packages.py:787、pricing.py:796。
- roles.py update_role 传 permission_ids 无缓存失效；assign_permissions(215) 有并发失效；users.py assign_roles(347) 无 invalidate，permission_cache 已导入（18 行）。
- `test_roles_api.py` update_role 用例只传 name/description，删除 permission_ids 不破坏测试。
- _check_permission 包含集 `["read","write","delete","create","update"]` + `system:audit_read` 死分支；全仓无端点 require `system:audit_read`，manage 模块端点均直接 require `:manage` → 澄清零行为变化。

## 权限码设计

新码 `sync_tasks:manage`（module=system）：

| 端点 | 权限码 | 理由 |
|------|--------|------|
| POST /analytics/consumption/sync | `sync_tasks:manage` | force_overwrite 全量同步是破坏性运维操作 |
| POST /sync-tasks、POST /sync-tasks/<id>/cancel | `sync_tasks:manage` | 同上 |
| GET /sync-tasks（list/stats/get/progress/details）、GET /sync-logs（2 端点） | `system:view` | 与同步日志页现有菜单门控一致 |

预置角色策略：运营经理/销售经理**不授** `sync_tasks:manage`（与 seed 现行「import 不预授」惯例一致；运营经理若需手动同步属产品决策，见 PRD Assumptions）。

## 缓存失效修复

- `PUT /roles/{id}` 删 permission_ids → 权限变更唯一入口 `POST /roles/{id}/permissions`（已失效该角色全部用户缓存）。双入口必漏失效，收敛为单入口。
- `POST /users/{id}/roles` assign_roles：success 后 `await permission_cache.invalidate(user_id)`，与 delete_user(287 行) 同款模式。

## seed --sync-permissions 设计

```
argparse: --sync-permissions（store_true，与 --reset 互斥使用时优先 sync 分支）
流程：
  1. upsert ALL_PERMISSIONS 每条（按 code 查：存在→更新 name/description/module；不存在→insert）
  2. 查询「超级管理员」角色 → 关联全部权限（role_permissions 已关联则跳过，幂等）
  3. commit 后失效 cache:permissions:*（复用 seed 尾部现有失效逻辑）
约束：不删除任何权限/关联；不触碰预置业务角色；无 DB 变更（纯数据同步）
```

## 前端设计要点

- **导出闭环**：`api/analytics.ts` 新增 `exportHealthWarningList(params?)` 用 `fetchExport` 风格（api.get + responseType blob + LONG_RUNNING_REQUEST_TIMEOUT）；Health.vue 下载用 `URL.createObjectURL` + a 标签 click（参照仓库既有下载实现，若 `useExportAction` 等 composable 可复用则复用，实施时以现有模式为准）。
- **搜索过滤**：`filterPermissionsByKeyword` 纯函数放 permissionGroups.ts（可单测）；`permissionGroups` computed = `buildPermissionGroups(filtered)`；全选/取消全选基于过滤后集合（与「已选 x/y」计数一致，均基于当前过滤结果——与现状语义一致：现状全选作用于全部权限，改为作用于过滤结果属预期行为收窄，弹窗内搜索后全选只应作用于可见项）。
- **高危标识**：模块级常量 + `class.permission-item--dangerous`（border-left: var(--warning)）+ a-tooltip。CSS 变量已定义于项目主题。
- **AppSidebar**：billing/analytics 父级 div.nav-parent 与 subnav 按钮加 v-if；useAppLayout navSections 子项加 permission（filterItems 已有，父级无可见子项自动隐藏——但注意 AppSidebar 是硬编码模板不消费 navSections，故 AppSidebar 必须显式加 v-if；两处都要改）。

## 风险与回滚

| 风险 | 缓解 |
|------|------|
| 新权限码导致集成测试 403 | 按 PLAN Assumptions：补 PERMISSION_ROWS 或改 admin token，禁止放宽端点 |
| 前端门控误伤（如侧边栏整组消失） | 运营经理预置角色已含 billing:view/analytics:view；验收 6 用只有 customers:view 的新角色验证 |
| `--sync-permissions` 竞争 | select-then-insert；若遇 IntegrityError 重查（get_or_create 模式已有） |
| _check_permission 语义变更 | 全仓无 manage 通配放大依赖、无 audit_read require，零行为变化；drift/单测兜底 |
| deploy 破坏性 | 全部为增量：新码 upsert、端点加 stricter 校验、前端加门；回滚 = revert 本分支 |

## 交付边界

分支 `role-permission-hardening` → PR 至 main。验收证据：pytest 输出、drift 变异验证记录、浏览器/API 端到端结果记录于 implement.md「验证记录」节。
