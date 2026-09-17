# Better Harness Task-Loop Report

## At a Glance

- Loop Effectiveness: 66/100 (changes only after comparable later task outcomes)
- Asset Health / Repair Progress: 29/100 (2 verified, 0 partial, 5 pending)
- Demonstrated autonomy radius: R1 (observed; Medium confidence)
- Strongest loop: 改动验证 (Used in a real task)
- Largest observed leak: 可靠交付 — 窗口内没有任何交付验收证据：闭合与恢复的 Task Episode 均为 0，交付证据列表为空。
- Top expected gain: 验收边界在规则与实施之间不再分裂，agent 收到的覆盖率下限可被机械验证。

## What You Can Rely On Today

- 验证行为是被观测到的执行而非仅配置：窗口内 218 次 pytest 调用、38 次发生在编辑之后的验证，且测试资产跟随业务代码同频变更。
- pre-commit 钩子正确遵守了项目的 Python 环境约定：pytest-unit 与 vitest 以 pre-push 阶段运行，脚本显式使用后端虚拟环境解释器而非依赖 PATH。
- 指令与规则资产覆盖面宽：根 AGENTS.md 路由 Trellis 工作流与技能目录，.omp/AGENTS.md 按层引用架构、目录、命令、约定、文件、运行时、测试、agent、重构共 9 条规则。

## What You Gain Next

- 改动验证: 验收边界在规则与实施之间不再分裂，agent 收到的覆盖率下限可被机械验证。 Smallest move: 把 .omp/RULES.md 的覆盖率规则与 CI 实际门禁收敛到同一个阈值。
- 任务理解: 五套 agent 配置目录都能从入口发现，硬规则不再取决于 provider 是否加载 .omp/。 Smallest move: 在根指令文件的托管块之外补一行指向 .omp/ 与 .catpaw/ 的路由。
- 可靠交付: 至少一次改动的验收结论可在仓库内复核，交付边界不再只存在于会话里。 Smallest move: 让会阻断合并的检查产出一个随运行保存的验收记录。



### Why these moves matter

### 硬规则声明的覆盖率门槛未被 CI 实施，实际阻断线只有声明值的一半
- Priority: Medium · Evidence: static evidence only
- Reason: 事实：.omp/RULES.md 作为始终附着的硬规则声明「CI 要求测试覆盖率 ≥50%（--cov-fail-under=50）」。逐一核验 .github/workflows/ 全部 6 个文件后，唯一带覆盖率阈值的是 pr-checks.yml 单元测试作业，参数为 --cov-fail-under=25；同一文件的集成测试作业与 backend-integration.yml 的集成测试只生成 term-missing 报告而不设阈值；ci.yml 的单元测试完全不测量覆盖率。推断：每次会话都被注入「下限 50%」这一验收边界，而真正能阻断合并的门槛是 25%，两者相差一倍；并且「≥50%」没有任何机械化检查可以验证或修复。归属：实测单元覆盖率 32% 低于 50%，提升实施门槛会立即破坏所有 PR，因此唯一安全收敛方向是把声明收敛到实施值 25%。不确定度：低——两侧都是静态配置且已打开核验；无法确定团队意图是把 CI 提到 50% 还是把规则下调到 25%，因此修复只要求对齐而不指定方向。
- Expected Output:
  1. 让 .omp/RULES.md 声明的覆盖率门槛与 CI 实际执行的阈值收敛为同一个数值。

### 根指令文件只路由五套 agent 配置中的两套，承载硬规则的 .omp/ 与 .catpaw/ 零提及
- Priority: Medium · Evidence: static evidence only
- Reason: 事实：仓库并存 .agents/、.catpaw/、.codex/、.omp/、.trellis/ 五套 agent 配置目录。核验根 AGENTS.md（2895 字节，仅 TRELLIS 与 CODEGRAPH 两段）后统计提及次数：trellis 7、agents 2、codex 1、omp 0、catpaw 0。承载项目硬规则的 .omp/AGENTS.md、.omp/RULES.md 与 .omp/rules/ 下 14 个规则文件因此不在根指令文件的路由内；反向也不通——.omp/AGENTS.md 全文仅 1 处 AGENTS.md 匹配且指向用户级全局文件，不引用根 AGENTS.md 或 .trellis/。.catpaw/rules/codebase-indexing.md 标记为始终生效，同样没有索引入口。推断：同一仓库在不同 agent 工具下会装载不同的规则集合，只加载 .omp/ 之外目录树的会话看不到事务、权限、覆盖率、Python 版本、并发安全与 pre-commit 环境这六条硬规则。资产清单只把根 AGENTS.md 计为唯一 Rules surface（count=1），使读者进一步低估真实的指令层数（实测至少 1 个根文件 + 1 份项目指南 + 1 份硬规则 + 14 个规则文件）。归属：根 AGENTS.md 中托管块之外的可保留区域，以及 .omp/rules/README.md 的索引。不确定度：中——本次运行的注入内容包含 .omp/AGENTS.md，说明当前 provider 会加载它；缺口影响的是依赖根指令文件导航的其它 provider，以及与目录实况不符的覆盖计数。
- Expected Output:
  1. 根指令文件在托管块之外增加指向 .omp/ 硬规则入口与 .catpaw/ 规则的一行路由，使五套配置目录都可从入口发现。

### trellis-break-loop 的模板同步步骤指向仓库中不存在的目录
- Priority: Low · Evidence: static evidence only
- Reason: 事实：.agents/skills/trellis-break-loop/SKILL.md 的收尾小节要求「After updating .trellis/spec/, sync to src/templates/markdown/spec/」。核验仓库：src/templates/ 与 src/templates/markdown/spec/ 均不存在，仓库根下也没有 src/ 目录。推断：该步骤在被触发时无法完成预期的写回——要么在项目之外创建目录，要么静默跳过；两种情况下 .trellis/spec/ 的更新都不会同步到任何消费方，形成一条永远不生效的指令。归属：.agents/skills/trellis-break-loop/SKILL.md 的模板同步步骤。不确定度：低——路径两侧都已打开核验；不确定该目录是被迁移到别处还是该步骤本身已作废，因此修复只要求让指令与仓库实况一致或删除该步骤。
- Expected Output:
  1. skill 的收尾步骤或指向仓库中真实存在的同步目标，或从流程中移除，不再留下指向空路径的动作。

### 30 天窗口内没有交付验收证据，闭合与恢复的 Task Episode 均为 0
- Priority: Medium · Evidence: not observed in this boundary
- Reason: 事实：会话证据边界的交付证据列表为空，episode 覆盖统计中闭合数与恢复数均为 0，同时 46 个 episode 里有 34 个发生过编辑。项目侧交付机制是存在的——unit、integration、端到端与部署共 6 条工作流，加上 pre-push 阶段的 pytest-unit 与 vitest 钩子——但本窗口没有采集到任何一次合并、部署、审批或恢复结果。推断：交付边界靠什么判定、失败后由谁恢复，在现有证据里没有答案，使「改动是否被真正接受」只能停留在推测层。归属：交付验收证据不需要新增流程，最小落点是把 PR 检查结论或合并结果写进可复核的产物。不确定度：中——证据通道自述不打开外部检查与 PR 系统，因此这首先是证据缺口；但项目确实有 6 条工作流，无法排除机制正常而只是未被观测。
- Expected Output:
  1. 至少一次改动带有可复核的验收记录：检查结论、合并判定或恢复结果三者之一被写入仓库内可读的产物。

### 从事故提炼的条件规则未进入规则索引，无法被检索或审计
- Priority: Low · Evidence: static evidence only
- Reason: 事实：.omp/rules/ 下有 14 个条目。.omp/AGENTS.md 以引用形式列出其中 9 个，另外 4 个带 condition 与 scope 前置字段的运行时条件规则未被任何指令文件引用：批量重复编辑、删除模型前的引用检查、Vue 编辑的完整路径、以及文件损坏时停止重写的退出协议。.omp/rules/README.md 自称项目规则索引，其清单只列出 10 条，漏掉其中 3 条条件规则。这些规则正文都记录了具体事故来源，例如逐文件手动编辑导致三次以上重复往返。推断：这类防护的可发现性完全依赖运行时条件正则命中，索引不完整使维护者与 agent 都无法审计覆盖范围，也无法确认某条防护会不会被注入。归属：.omp/rules/README.md 的索引清单，必要时区分始终生效规则与条件规则。不确定度：中——索引与目录的差异已逐一核验；运行时是否无条件装载全部规则文件无法从仓库判定，因此不断言这些规则当前已经失效。
- Expected Output:
  1. .omp/rules/README.md 的清单与目录实况逐条对齐，并标明每条规则是始终生效还是按条件触发。

### 三个长 Skill 的渐进式披露问题连续三次审查被记录但未修复
- Priority: Low · Evidence: static evidence only
- Reason: 事实：trellis-update-spec（356 行）、trellis-brainstorm（200 行）、trellis-break-loop（188 行）都是线性长文件且不含本地引用或 references/ 子目录；同批的 trellis-session-insight 采用短主体加 references/ 的组织方式，是本仓库内已存在的正向范式。本问题在 docs/better-harness 下 2026-09-12-01 与 2026-09-13-01 两次审查报告中都被保留为 Low 项，后者还明确标注了上次报告同题未修复；本次独立复核确认它依然存在。推断：真正未闭合的不是这三个文件本身，而是已报告项没有进入可追踪状态——同一问题连续三次进入报告，既没有被修复，也没有被显式判定为不需要修复。归属：三个 Skill 的引用组织，以及让已报告项能被追踪到关闭的最小机制。不确定度：低——lint 提示、文件行数、目录结构与三份报告的文本都已逐一核验；没有测量运行时的上下文成本，因此不断言实际加载开销。
- Expected Output:
  1. 三个长 Skill 采用与仓库内已有范式一致的按需引用组织，或被明确记录为不需要修复并关闭该项。

### 会话候选发射连续两个窗口为空，重复工作与干净窗口都无法判定
- Priority: Low · Evidence: not observed in this boundary
- Reason: 事实：本窗口的会话信封中 admission 层 emittedCandidates 为 0，emittedClasses 为空对象，而可分发类里已有 46 条 validation-repair、57 条 operation-control、41 条 read-only-work 等共 166 条候选；omitted.candidateBudget 吞掉 93 条，checkBudget 吞掉 367 条；observationCoverage 的九项计数全为 0；93 条请求根只有 5 条带 candidateRef。另核验到 93 条请求根中有 57 条是代理自派发的子任务提示格式，却未被 selfAnalysis 过滤。上一窗口的 docs/better-harness/2026-09-13-01 报告已记录过同类的候选截断问题并判定无法识别重复工作流。推断：两个窗口都无法区分稳定重复工作、干净窗口与维护漂移，因此任何基于会话的重复需求结论都会混淆代理内部派发与用户意图。归属：会话采集侧对请求根的来源分类与候选发射，而不是项目代码。不确定度：中——发射为空与覆盖为零都是信封内的观测值；但归因于采集端还是选择端无法从信封判定。
- Expected Output:
  1. 会话证据再次采集时 emittedClasses 非空、自派发的子任务提示被单独归类，并至少有一条带有关联检查与结果的候选。

## Five Lifecycle Dimensions

| Dimension | What the evidence proves | Evidence boundary | Summary | Boundary / blocker |
| --- | --- | --- | --- | --- |
| 任务理解 | It is connected | connected, not seen in a task yet | 指令资产丰富且已接线，但五套配置目录只有两套可从入口发现。 | 承载硬规则的 .omp/ 未被根指令文件路由，另有 4 条条件规则不在任何索引内。 |
| 可控执行 | It is connected | connected, not seen in a task yet | 启动与验证入口齐全，仍有一条指令指向不存在的目录。 | trellis-break-loop 的收尾步骤指向仓库中不存在的目录，权限装饰器覆盖也没有机械检查。 |
| 改动验证 | Used in a real task | used, awaiting accepted result evidence | 验证被真实执行，覆盖率门禁的声明与实施数值不一致。 | 硬规则声明覆盖率下限 50% 而唯一带阈值的 CI 作业执行 25%，验收边界在规则与实施之间分裂。 |
| 可靠交付 | It exists | static evidence only | 交付机制已配置，窗口内没有任何验收证据。 | 窗口内闭合与恢复的 Task Episode 均为 0，交付验收证据列表为空。 |
| 经验沉淀 | It exists | not observed in this boundary | 沉淀资产活跃，两条缺口在历次报告中重复出现且未闭合。 | 无干预台账与可比的后续窗口，且两条缺口已在历次报告中重复出现。 |

## The 15 Small Checks

| Dimension | Small check | What the evidence proves | Evidence boundary |
| --- | --- | --- | --- |
| 任务理解 | 意图与验收 | It is connected | connected, not seen in a task yet |
| 任务理解 | 相关上下文 | It is connected | static evidence only |
| 任务理解 | 范围边界 | It exists | static evidence only |
| 可控执行 | 可复现启动 | It is connected | connected, not seen in a task yet |
| 可控执行 | 受支持操作 | It is connected | static evidence only |
| 可控执行 | 权限边界 | It exists | static evidence only |
| 改动验证 | 相关验证 | Used in a real task | used, awaiting accepted result evidence |
| 改动验证 | 故障诊断与修复 | Used in a real task | used, awaiting accepted result evidence |
| 改动验证 | 修复后复验 | It exists | static evidence only |
| 可靠交付 | 交付验收 | Not observed yet | not observed in this boundary |
| 可靠交付 | 高风险审批 | It exists | static evidence only |
| 可靠交付 | 回滚或恢复 | It exists | static evidence only |
| 经验沉淀 | 生命周期机会识别 | Used in a real task | not observed in this boundary |
| 经验沉淀 | 闭环工程化 | Not observed yet | not observed in this boundary |
| 经验沉淀 | 长期验证 | Not observed yet | not observed in this boundary |

## Evidence and Boundaries

- Episode coverage: 46 episodes, 34 edited, 0 closed, 0 repaired-and-passed
- Model: agent-work-loop-v4
- Session selection: stratified; 40 sessions analyzed of 72 eligible sessions; Medium confidence
- Delivery grades observed: not observed
- Source gaps: not observed
- Learning comparison: Needs a comparison; 0 declared intervention(s)
