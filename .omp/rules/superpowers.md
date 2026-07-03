## Superpowers & OMP Workflow

### 适用范围

本项目使用 Superpowers 作为 agentic software development methodology，并在 OMP 环境中执行。Superpowers 负责规定“什么时候必须调用技能、如何规划、如何调试、如何验证”；OMP 负责提供项目工具、IDE 上下文、子代理、CodeGraph、context-mode、文件读写与命令执行能力。

### 指令优先级

1. **用户显式指令和本项目规则优先**：`.omp/AGENTS.md`、`.omp/rules/*.md`、`.omp/RULES.md`、当前用户消息高于 Superpowers 技能。
2. **Superpowers 技能次之**：当技能与默认 agent 行为冲突时，按技能执行。
3. **默认模型习惯最低**：不得用“只是简单问题”“先快速看一下文件”等理由跳过技能检查。

### 会话启动规则

- 每次收到用户任务后，先判断是否有 Superpowers 技能适用；只要有 1% 可能适用，就必须先读取/激活该技能，再进行澄清、探索、计划或实现。
- 在 OMP 中读取技能必须使用 `skill://<skill-name>` 或平台提供的技能加载机制；禁止凭记忆复述技能内容。
- 若任务是子代理收到的明确执行子任务，遵循该子任务说明；`using-superpowers` 中的主会话启动流程可跳过，但仍必须使用与子任务直接相关的技能。

### 技能选择矩阵

| 场景 | 必须优先使用的技能 | 项目内执行规则 |
|------|--------------------|----------------|
| 新功能、行为变更、组件/页面/API 设计 | `brainstorming` | 先澄清目标与约束；若用户明确要求直接实现且需求已完整，记录假设后继续 |
| Bug、测试失败、异常行为 | `systematic-debugging` | 先定位根因，禁止未证明根因前直接改代码 |
| 需要写代码修复或新增行为 | `test-driven-development`（若适用） | 结算管理金额/余额/账单逻辑严格 TDD；其他模块至少补充能验证新行为的测试或说明无需测试的原因 |
| 多步骤或跨文件实现 | `writing-plans` | 先写可执行计划，计划必须列明文件、符号、步骤、验证命令 |
| 执行已有计划 | `executing-plans` 或 `subagent-driven-development` | 独立任务优先 `subagent-driven-development`；顺序强依赖任务使用 `executing-plans` |
| 2 个以上独立文件/模块可并行调查或实现 | `dispatching-parallel-agents` | 使用 OMP `task` 并行派遣；每个子代理必须有明确 Target/Change/Acceptance |
| 完成修复或功能后准备声明完成 | `verification-before-completion` | 必须运行能覆盖新行为的检查后，才可说“完成/修复/通过” |
| 请求提交代码 | `git-commit` | 先检查 diff，按 conventional commit 生成提交信息 |
| 需要外部库/API/框架文档 | `context7-mcp` 或 context-mode fetch/index | 优先读取官方文档，不凭训练数据猜测新版本 API |

### OMP 工具映射

- **技能读取**：使用 `read` 读取 `skill://<skill-name>`；不得直接读取技能目录文件来绕过技能激活语义。
- **代码定位**：若仓库根目录存在 `.codegraph/`，理解或定位代码时先用 CodeGraph；只有 CodeGraph 未覆盖、配置/文档文件、或需要编辑精确行号时再用 `read`/`grep`。
- **大输出处理**：分析日志、测试输出、依赖树、批量命令、网页内容时使用 context-mode：`ctx_execute`、`ctx_execute_file`、`ctx_batch_execute`、`ctx_fetch_and_index`、`ctx_search`。禁止用 `curl`/`wget` 或原始网页读取把大段 HTML/日志灌入上下文。
- **轻量并行 I/O**：多个互不依赖的读取可用 OMP 并行工具；需要完整推理的独立调查使用 `task` 子代理。
- **用户偏好**：文件修改前必须先读取；不确定用户意图时主动询问；所有会话内回复使用中文。

### 项目硬规则与 Superpowers 的结合

- 后端写操作仍必须使用 `async with db_session.begin():`；所有 API 端点仍必须添加 `@auth_required`。Superpowers 技能不能降低这些项目硬规则。
- 结算管理、余额扣款、账单金额、客户确认、付款状态等敏感路径必须把 `systematic-debugging`、`test-driven-development`、`verification-before-completion` 串起来执行：先证据定位，再失败测试，再最小实现，再验证。
- 前端 Vue 代码继续遵守 `<script setup lang="ts">`、完整 TypeScript 类型、禁止无理由 `any`、`npm run type-check` 0 errors 的规则。
- 计划或实现中如需新增规则、文档或测试，必须复用现有目录风格；不得引入新的规则入口文件，除非同时在 `.omp/AGENTS.md` 中引用。

### 子代理使用规范

- 满足以下任一条件时优先并行派遣：2 个以上独立模块调查、前后端可独立验证、多个测试策略可独立比较、外部文档与本地代码可并行读取。
- 每个子代理任务必须包含 `# Target`、`# Change`、`# Acceptance`；禁止派遣“随便看看”“帮我分析一下”这类无验收标准任务。
- 子代理不得运行项目级格式化、lint 或完整测试套件；主代理在最终阶段统一运行。
- 子代理输出只作为证据输入，主代理负责整合决策；若子代理结论与已读代码冲突，以当前实际文件内容为准并重新读取确认。

### 计划模式规则

- 在 Plan mode 中，只能做只读调研和写入指定 plan 文件；不得创建、编辑、删除其他文件，不得运行安装、迁移、提交等状态改变命令。
- 计划文件必须是执行规格，不是设计讨论：每一步包含目标文件、具体符号或区域、精确行为、验证方式和失败时 fallback。
- 若计划获批后进入执行，必须先读取计划文件，再按 `executing-plans` 或 `subagent-driven-development` 执行；不得依赖规划会话记忆。

### 验证与完成声明

- 任何“完成/修复/通过”的表述前，必须有一条与新行为直接相关的验证证据。
- 验证命令按变更范围选择：后端优先运行具体 pytest；前端类型变更运行 `npm run type-check`；UI 行为变更至少给出手动路径或 E2E/组件测试；规则/文档变更至少检查引用链和关键条款是否存在。
- 若无法运行验证，必须明确说明未验证原因、影响范围、以及下一步应运行的具体命令。
