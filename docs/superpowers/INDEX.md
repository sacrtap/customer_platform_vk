# Superpowers 工作流索引

> 本目录收录 AI 辅助开发工作流 (Superpowers) 产出的设计规格与实现计划。

---

## 设计规格 (specs/)

设计规格定义系统架构、功能需求和接口规范。

| 文件 | 日期 | 说明 |
| ---- | ---- | ---- |
| [2026-04-01-customer-platform-design.md](specs/2026-04-01-customer-platform-design.md) | 2026-04-01 | 客户运营中台系统设计 |
| [2026-04-01-customer-platform-implementation-plan.md](specs/2026-04-01-customer-platform-implementation-plan.md) | 2026-04-01 | 客户运营中台实现计划 |
| [2026-04-03-customer-groups-design.md](specs/2026-04-03-customer-groups-design.md) | 2026-04-03 | 客户分组功能设计 |
| [2026-04-06-frontend-redesign.md](specs/2026-04-06-frontend-redesign.md) | 2026-04-06 | 前端重设计规格 |
| [2026-04-12-customer-detail-redesign.md](specs/2026-04-12-customer-detail-redesign.md) | 2026-04-12 | 客户详情重设计规格 |

## 实现计划 (plans/)

实现计划将设计规格拆解为可执行的任务步骤。

| 文件 | 日期 | 关联规格 | 说明 |
| ---- | ---- | -------- | ---- |
| [2026-04-01-phase0-backend-initialization.md](plans/2026-04-01-phase0-backend-initialization.md) | 2026-04-01 | customer-platform-design | Phase 0: 后端初始化 |
| [2026-04-02-permission-checker-implementation.md](plans/2026-04-02-permission-checker-implementation.md) | 2026-04-02 | customer-platform-design | 权限检查器实现 |
| [2026-04-03-customer-groups-implementation.md](plans/2026-04-03-customer-groups-implementation.md) | 2026-04-03 | customer-groups-design | 客户分组实现 |
| [2026-04-07-ux-ui-improvements.md](plans/2026-04-07-ux-ui-improvements.md) | 2026-04-07 | frontend-redesign | UX/UI 改进 |
| [2026-04-09-customer-management-optimization.md](plans/2026-04-09-customer-management-optimization.md) | 2026-04-09 | - | 客户管理优化 |
| [2026-04-12-customer-detail-redesign.md](plans/2026-04-12-customer-detail-redesign.md) | 2026-04-12 | frontend-redesign | 客户详情重设计 |

---

## 工作流说明

1. **Spec 先行**: 每个功能先创建设计规格 (`specs/`)
2. **Plan 跟进**: 基于规格拆解为实现计划 (`plans/`)
3. **执行跟踪**: 计划中的任务按 Phase 逐步执行
4. **归档管理**: 已完成的计划保持归档，便于追溯
