# 客户运营中台 - 文档导航

> 最后更新: 2026-09-16

---

## 快速链接

| 文档类型       | 路径                                    | 说明                     |
| -------------- | --------------------------------------- | ------------------------ |
| **用户手册**   | [user-manual.md](user-manual.md)        | 面向最终用户的使用指南   |
| **开发指南**   | [guides/](guides/)                      | 本地环境搭建、数据库迁移等 |
| **设计文档**   | [design/](design/)                      | 设计规范、样式规范       |
| **方案与计划归档** | [specs/](specs/)                    | 按日期的功能方案、bug 根因、执行计划（含原 Superpowers 历史归档 48 篇） |
| **数据库文档** | [database/](database/)                  | 数据库变更日志           |
| **性能优化**   | [performance/](performance/)            | 查询优化、缓存、监控     |
| **测试文档**   | [testing/](testing/)                    | 测试计划、报告、环境配置 |
| **前端组件**   | [frontend/components.md](frontend/components.md) | Vue 组件清单与复用指南 |
| **技术债务**   | [technical_debt/](technical_debt/)              | 技术债跟踪             |
| **原型**       | [prototypes/](prototypes/)              | HTML 原型文件            |

---

## 开发指南

| 文件                                              | 说明             |
| ------------------------------------------------- | ---------------- |
| [agents-guide.md](guides/agents-guide.md) | **Agent 开发指南** (完整命令/env/git/工作流) |
| [local-setup-guide.md](guides/local-setup-guide.md) | 本地环境搭建指南 (PostgreSQL + Redis + 后端 + 前端) |
| [database-migration-guide.md](guides/database-migration-guide.md) | 数据库迁移指南 |
| [test-optimization-guide.md](guides/test-optimization-guide.md) | 测试优化指南 |

## 设计文档

| 文件                                              | 说明             |
| ------------------------------------------------- | ---------------- |
| [DESIGN-SPEC.md](design/DESIGN-SPEC.md)           | 设计规格说明     |
| [QUICK-REFERENCE.md](design/QUICK-REFERENCE.md)   | 设计快速参考     |
| [TABLE-STYLE-UPDATE.md](design/TABLE-STYLE-UPDATE.md) | 表格样式更新记录 |
| [Design System MASTER](design/design-system/customer-platform-vk/MASTER.md) | 设计系统主文件 |

## 性能优化

| 文件                                                          | 说明             | 状态 |
| ------------------------------------------------------------- | ---------------- | ---- |
| [README.md](performance/README.md)                              | 性能优化文档索引 | -    |
| [db-query-optimization.md](performance/db-query-optimization.md) | 数据库查询优化   | ✅ 完成 |
| [query-optimization-examples.md](performance/query-optimization-examples.md) | 查询优化示例     | ✅ 完成 |
| [redis-cache-analysis.md](performance/redis-cache-analysis.md) | Redis 缓存分析   | ✅ 完成 |
| [structured-logging-config.md](performance/structured-logging-config.md) | 结构化日志配置   | ✅ 完成 |
| [sentry-integration-plan.md](performance/sentry-integration-plan.md) | Sentry 集成计划  | 📋 计划中 |
| [test-optimization-guide.md](../guides/test-optimization-guide.md) | 测试优化指南     | ✅ 完成 |

## 测试文档

### 测试计划
- [test-plan.md](testing/plans/test-plan.md) - 通用测试计划
- [phase0-7-test-plan.md](testing/plans/phase0-7-test-plan.md) - Phase 0-7 测试计划
- [customer-page-test-plan.md](testing/plans/customer-page-test-plan.md) - 客户页面测试计划
- [role-permission-test-plan.md](testing/plans/role-permission-test-plan.md) - 角色权限测试计划

### 测试报告
- [unit-test-report.md](testing/reports/unit-test-report.md) - 单元测试报告
- [customer-page-test-report.md](testing/reports/customer-page-test-report.md) - 客户页面测试报告
- [role-permission-test-report.md](testing/reports/role-permission-test-report.md) - 角色权限测试报告
- [final-fix-report.md](testing/reports/final-fix-report.md) - 最终修复报告
- [final-improvement-report.md](testing/reports/final-improvement-report.md) - 最终改进报告

### 测试环境
- [test-database-setup.md](testing/setup/test-database-setup.md) - 测试数据库配置

### 测试覆盖率
- HTML 覆盖率报告：运行 `make test-cov` 后在 `backend/htmlcov/index.html` 查看
- CI 覆盖率门禁：≥50%（全量口径：单元+集成 coverage 合并判定，以 `.github/workflows/pr-checks.yml` 为准）

### E2E 测试
- [前端 E2E 测试指南](../frontend/tests/e2e/README.md) - Playwright E2E 测试指南 (57 个客户管理测试)
- [HTML 测试报告](../frontend/tests/e2e/playwright-report/index.html) - 最新测试报告 (需运行测试后生成)

### 测试优化
- [测试优化指南](guides/test-optimization-guide.md) - 测试并行化、增量测试、fixture 优化

## 历史归档说明

原 Superpowers 工作流产出的设计规格与实现计划已于 2026-11-19 整体并入 [specs/](specs/)（48 篇：平台总设计、各功能设计、重构设计与执行计划；含 2 个已随功能移除而删除的文件的历史登记）。

---

## 文档规范

- **功能方案 / bug 根因 / 执行计划 / 历史设计归档** → `specs/`（命名 `YYYY-MM-DD-<slug>.md`，按 Context / Approach / Critical files & anchors / Verification 组织；2026-11-19 起含原 Superpowers 工作流迁移的 48 篇历史设计，样板 `2026-10-21-customer-usage-30d-cache-key.md`）
- **测试计划** → `testing/plans/`
- **测试报告** → `testing/reports/`
- **性能/优化** → `performance/`
- **开发指南** → `guides/`
