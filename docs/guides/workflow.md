# 开发工作流（历史指针）

> **状态**：历史文档。本文描述的 Superpowers + Oh-My-OpenAgent 五阶段流程自 2026-06 后不再使用，仅保留入口提示，请勿照做其中命令。

## 当前流程去哪看

- **任务生命周期**：`.trellis/workflow.md`（计划 → 执行 → 收尾的阶段索引与脚本）
- **硬规则与分工**：`.omp/RULES.md` 与 `.omp/rules/*.md`（事务、权限、覆盖率、环境等强制约定）
- **会话恢复**：`python3 ./.trellis/scripts/get_context.py`

## 历史产出去哪看

- **方案 / 根因 / 执行计划**：`docs/specs/`，按 `YYYY-MM-DD-<slug>.md` 归档（含 2026-11-19 从 `.omo` 蒸馏的 12 篇与从 `docs/superpowers` 迁移的 48 篇历史设计）
- **代码评审记录**：`docs/code-review/`（本地积累，不纳入版本控制）
- **技术债跟踪**：`docs/technical_debt/`

## 存量约定

新方案继续落 `docs/specs/YYYY-MM-DD-<slug>.md`，按 Context / Approach / Critical files & anchors / Verification / Assumptions 组织；结构样板见 `docs/specs/2026-10-21-customer-usage-30d-cache-key.md`。
