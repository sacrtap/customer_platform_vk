# Better Harness Task-Loop Report

## At a Glance

- Loop Effectiveness: 66/100 (changes only after comparable later task outcomes)
- Asset Health / Repair Progress: 0/100 (0 verified, 0 partial, 3 pending)
- Demonstrated autonomy radius: R2 (observed; medium confidence)
- Strongest loop: Not enough evidence difference to name one.
- Largest observed leak: 改动验证 — CI 门禁已自动执行集成验收且实际跑通，但会话内最终变更后的检查仍全部标记为 unreviewed，验收信号由 assistant-handoff 而非被审阅的相关检查承载。
- Top expected gain: 变更到最终验证的链路可被后续窗口审阅，验收信号不再是代理自述

## What You Can Rely On Today

- 集成测试已接入 PR 门禁并在真实 Postgres/Redis 上自动执行，本窗口 PR #24 的 Backend Integration Tests 与 Migration Test Gate 均实际跑通（CI 7/7 通过）
- billing 服务层五处失败路径已补齐携带客户标识与金额上下文的 error 日志，consume 重试耗尽与余额缺失场景可回推触发点
- correlation 中间件已启用：RequestIdFilter 挂接 root/命名 logger/lastResort 三层，响应头与日志均带稳定关联标识
- backend/app 包级上下文指令已落地：分层边界、billing 域特例、失败诊断链与受影响检查路由清晰
- 迁移测试在独立测试库执行真实 upgrade/downgrade 并断言与业务计算一致，migration-gate 以 paths-filter 阻断缺失测试与 heads 分叉
- pre-commit 环境规则合规化：pytest-unit 改用 $BACKEND_DIR/.venv/bin/python，收尾流程提交→finish-work 次序文档化

## What You Gain Next

- 改动验证: 变更到最终验证的链路可被后续窗口审阅，验收信号不再是代理自述 Smallest move: 为每个会话内变更记录被审阅的相关检查与验收结果，替代以 assistant-handoff 作为唯一验收信号
- 经验沉淀: Skill 正文进入上下文时按需加载，长文件触发开销可维护 Smallest move: 将三个长 Trellis Skill 抽取渐进式 references/ 结构，与 trellis-meta 的组织方式对齐



### Why these moves matter

### 会话内最终变更后的检查全部 unreviewed，验收信号由 assistant-handoff 承载
- Priority: Medium · Evidence: connected, not seen in a task yet
- Reason: CI 门禁已自动执行集成验收且本窗口实际跑通（PR #24 的 Backend Integration Tests 与 Migration Test Gate 均 pass），但窗口内 4/5 候选在最终变更后运行的 pytest/lint/typecheck 全部标记为 after-final-change-unreviewed，0 条 reviewed-relevant-check、0 条 user-feedback、0 条 provider-confirmed-delivery；所有 acceptanceSignals 均由 assistant-handoff 承载。后果是会话内的验证结果无法被后续窗口审阅，验收边界依赖代理自述而非可审计的相关检查。机制已 Wired，缺口在会话内审阅信号未与变更绑定。
- Expected Output:
  1. 会话内变更→受影响检查→被审阅结果的链路可被后续窗口审计
  2. 验收信号来自可关联的相关检查而非代理自述

### 三个 Trellis Skill 为长文件且无渐进式引用，与 trellis-meta 组织方式不一致
- Priority: Low · Evidence: not observed in this boundary
- Reason: lint advisory 确定性：trellis-brainstorm (200 行)、trellis-break-loop (188 行)、trellis-update-spec (356 行) 均无本地 Markdown 相对链接或 references/ 子目录引用，rubricRef=Progressive Disclosure；同批 trellis-meta 已提供完整 references/ 树。后果是三个 Skill 每次触发都会把全部正文带进模型可见上下文，长文件维护与加载开销无渐进式缓解；lint advisory 只证明静态结构，未证实运行时成本，但组织方式不一致是确定性事实。上次报告同题未修复。
- Expected Output:
  1. 三个长 Skill 采用渐进式引用结构，入口与引用分离
  2. lint advisory 消除，正文行数下降

### requestRoots 缺失且候选截断，重复工作流判定保持 unknown
- Priority: Low · Evidence: not observed in this boundary
- Reason: 信封未提供 requestRoots 数组，reference 要求的 Phase 1 根聚类无法执行；11 个 candidate 被 candidateBudget 截断，5 个 noRequest；全部 5 个 emitted candidate 同属 contextGroup G1，按独立性约束不构成独立需求。后果是本窗口无法判定是否存在稳定重复工作流，procedureConfidence 全部为 unknown；这不是"无重复需求"的结论，而是证据缺失。若重复的 PR 检查修复、CI 验证边界决策等工作流确实存在，将无法路由到复用资产。
- Expected Output:
  1. 根聚类可执行，重复工作流判定可收敛
  2. 证据边界从 unknown 转为可检查

## Five Lifecycle Dimensions

| Dimension | What the evidence proves | Evidence boundary | Summary | Boundary / blocker |
| --- | --- | --- | --- | --- |
| 任务理解 | It is connected | connected, not seen in a task yet | 分层上下文路由完整，用户以方向微调推进而非纠错。 | 上下文路由完整但会话内使用证据不足，行为判定保持 wired-unobserved。 |
| 可控执行 | It exists | static evidence only | 环境路由完整，本窗口实测可复现启动与验证。 | 环境机制声明完整，运行时行使证据有限。 |
| 改动验证 | It is connected | connected, not seen in a task yet | CI 机械验证已接线并实际跑通，会话内审阅信号未闭合。 | CI 门禁已验证接线，会话内审阅信号缺口仍开放。 |
| 可靠交付 | It is connected | connected, not seen in a task yet | 合并前自动执行完整验证链，失败产物可审计。 | 交付机制完整，运行时交付证据限于本窗口单次合并。 |
| 经验沉淀 | Not observed yet | not observed in this boundary | 无运行中学习回路可验证，重复工作流判定受观测器缺口限制。 | 学习回路未运行，重复与维护判定均受证据边界限制。 |

## The 15 Small Checks

| Dimension | Small check | What the evidence proves | Evidence boundary |
| --- | --- | --- | --- |
| 任务理解 | 意图与验收 | It is connected | connected, not seen in a task yet |
| 任务理解 | 相关上下文 | It is connected | connected, not seen in a task yet |
| 任务理解 | 范围边界 | It exists | static evidence only |
| 可控执行 | 可复现启动 | It exists | static evidence only |
| 可控执行 | 受支持操作 | It exists | static evidence only |
| 可控执行 | 权限边界 | It exists | static evidence only |
| 改动验证 | 相关验证 | It is connected | connected, not seen in a task yet |
| 改动验证 | 故障诊断与修复 | It is connected | connected, not seen in a task yet |
| 改动验证 | 修复后复验 | It exists | static evidence only |
| 可靠交付 | 交付验收 | It is connected | connected, not seen in a task yet |
| 可靠交付 | 高风险审批 | It is connected | static evidence only |
| 可靠交付 | 回滚或恢复 | It exists | static evidence only |
| 经验沉淀 | 生命周期机会识别 | Not observed yet | not observed in this boundary |
| 经验沉淀 | 闭环工程化 | Not observed yet | not observed in this boundary |
| 经验沉淀 | 长期验证 | Not observed yet | not observed in this boundary |

## Evidence and Boundaries

- Episode coverage: 5 episodes, 3 edited, 0 closed, 0 repaired-and-passed
- Model: agent-work-loop-v4
- Session selection: all-eligible; 14 sessions analyzed of 14 eligible sessions; Medium confidence
- Delivery grades observed: not observed
- Source gaps: 信封未提供 requestRoots 数组，Phase 1 根聚类无法执行；11 个 candidate 被 candidateBudget 截断，重复工作流判定为 unknown 而非无重复; 摩擦到后果的链条未被记录（frictionConsequenceSignals 空），E4 的 16 次执行失败无法归因到具体机制; pi provider 下 Memory inventory 未实现（skipped pi memories），Memory 标题元数据不可用
- Learning comparison: Needs a comparison; 0 declared intervention(s)
