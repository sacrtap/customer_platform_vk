# 完整开发工作流

> **核心原则**：Superpowers 负责**规划和设计**，Oh-My-OpenAgent 负责**执行和追踪**。两者是上下游关系，不是竞争关系。

## 端到端流程总览

```
产品需求 → 技术方案 → 执行计划 → 开发执行 → 验证 → 收尾
   ↓          ↓          ↓          ↓          ↓        ↓
/create-prd  /brainstorming  Prometheus  /start-work  verification  finishing
  (PRD)       (技术设计)     (.omo/plans/)  + subagent  (运行验证)   (合并/清理)
```

## 阶段 1：产品需求（`/create-prd` 技能）

**何时使用**：新功能开发、重大功能变更

**产出物**：`docs/prd/YYYY-MM-DD-<feature-name>.md`

**流程**：
1. 加载 `/create-prd` 技能
2. 通过多轮问答收集需求（问题→用户→指标→范围→约束→优先级）
3. 生成完整 PRD 文档
4. 保存到 `docs/prd/` 目录

**PRD 包含**：
- 问题陈述和目标用户
- 成功指标（KPIs）
- 范围定义（In/Out of Scope）
- 功能需求（MoSCoW 优先级）
- 技术约束和依赖
- 风险分析（Pre-mortem）

## 阶段 2：技术方案（Superpowers `/brainstorming`）

**何时使用**：PRD 完成后，需要确定技术实现方案

**产出物**：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

**流程**：
1. 加载 `/brainstorming` 技能
2. 探索项目上下文（文件、文档、最近提交）
3. 提出 2-3 种技术方案，比较优缺点
4. 用户确认方案后，写入设计文档
5. 设计文档自审（占位符扫描、一致性检查、范围检查）
6. 用户审查设计文档
7. ⚠️ **停止于此**：不调用 writing-plans，将技术方案交给 Prometheus 生成执行计划

**关键原则**：
- 一次只问一个问题
- 优先使用选择题
- 严格 YAGNI（不建不必要的功能）
- 设计要模块化、可测试

**⚠️ 关键约束**：
- brainstorming 完成后，**不要**调用 `/superpowers:writing-plans`
- 技术方案文档确认后，直接交给 Oh-My-OpenAgent Prometheus 生成执行计划
- 这样避免两套计划系统（`docs/superpowers/plans/` 和 `.omo/plans/`）并存导致的执行混乱

## 阶段 3：执行计划（Oh-My-OpenAgent Prometheus）

**何时使用**：技术方案确定后，需要生成可执行的开发计划

**输入上下文**：
- PRD 文档（`docs/prd/`）
- 技术方案文档（`docs/superpowers/specs/`）
- 项目现有代码模式（通过 explore/librarian agent 自动调研）

**产出物**：`.omo/plans/<plan-name>.md`

**实际流程**（Prometheus Interview Mode）：
1. 用户确认技术方案文档后，告知 Prometheus "基于此方案创建执行计划"
2. Prometheus 进入 Interview Mode，提出 2-4 个澄清问题（范围/测试策略/边界）
3. 需求明确后 Prometheus 自动 transition 到 Plan Generation
4. 计划保存至 `.omo/plans/<plan-name>.md`

**为什么需要 Interview Mode**：
- 防止 Prometheus 对技术方案做错误假设
- 确保测试策略（TDD/tests-after/none）在执行前确定
- 明确 IN/OUT 边界，防止范围蔓延

**流程**：
1. 用户将 PRD 和技术方案文档作为上下文
2. 调用 Prometheus 规划顾问
3. Prometheus 生成 Sisyphus 格式计划（`.omo/plans/`）
4. 计划包含：任务分解、依赖关系、并行波次、验收标准、QA 场景

**计划格式**（Sisyphus 格式）：
- 任务编号：`1.`, `2.`, `3.`（裸数字，非 `T1.`/`Task 1.`）
- 最终验证波次：`F1.`, `F2.`, `F3.`, `F4.`
- 每个任务包含：What to do、Agent Profile、Parallelization、References、Acceptance Criteria、QA Scenarios

## 阶段 4：开发执行（Oh-My-OpenAgent `/start-work`）

**何时使用**：计划生成完成后

**流程**：
1. 运行 `/start-work <plan-name>`
2. Sisyphus 读取 `.omo/plans/<plan-name>.md`
3. 按波次派遣 subagent 执行任务
4. 每个任务完成后收集证据到 `.omo/evidence/`
5. 最终验证波次（F1-F4）并行审查
6. 用户确认后完成

**Subagent 派遣原则**：

- **领域知识任务** → 优先使用项目自定义 agent（见 `.omp/rules/agents.md`）
- **通用任务** → 使用 OMP 标准 subagent（`explore`, `oracle`, `quick_task` 等）
- **并行 I/O** → 优先使用 `eval` 的 `parallel()` 而非 `task`

详见 `.omp/rules/agents.md` 和全局配置 `~/.omp/agent/AGENTS.md`。

## 阶段 5：验证确认（Superpowers）

**何时使用**：开发完成后，提交代码前

**流程**：
1. 加载 `/superpowers:verification-before-completion` 技能
2. 运行验证命令（测试、lint、构建）
3. 确认输出后再声称成功
4. 加载 `/superpowers:finishing-a-development-branch` 技能
5. 提供合并选项（merge/PR/cleanup）

**铁律**：
- **没有验证证据，不得声称成功**
- 必须在本轮对话中运行验证命令，不能使用之前的结果
- 验证失败 → 修复 → 重新验证 → 才能声称成功

**与 Oh-My-OpenAgent Final Wave 的关系**：
- Final Wave（F1-F4 并行审查）负责：代码质量审查、计划合规检查、范围检查、手动 QA
- `verification-before-completion` 负责：运行验证命令（pytest/ruff/playwright/build），确认输出后再声称成功
- 两者互补：Final Wave 审代码质量，verification 审运行结果
- 推荐顺序：Final Wave 通过后 → 运行 verification → 确认输出 → finishing-a-development-branch

**推荐验证顺序**：
1. Final Wave（F1-F4）并行审查 → 全部 APPROVE
2. pre-commit 完整检查 → `pre-commit run --all-files`
3. verification-before-completion → 运行 pytest/ruff/playwright
4. CI 覆盖率确认 → `make test-cov` 确认 ≥50%
5. finishing-a-development-branch → 合并选项
