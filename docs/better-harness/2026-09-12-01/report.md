# Better Harness Task-Loop Report

## At a Glance

- Loop Effectiveness: 57/100 (changes only after comparable later task outcomes)
- Asset Health / Repair Progress: 86/100 (6 verified, 0 partial, 1 pending)
- Demonstrated autonomy radius: R2 (observed; medium confidence)
- Strongest loop: Not enough evidence difference to name one.
- Largest observed leak: 改动验证 — 窗口内没有任何一次针对最终变更的被审阅检查，故障路径也缺少可关联的诊断输出。
- Top expected gain: billing 核心链的数据库事务路径在合并前自动执行真实验收，变更后相关检查有确定路由

## What You Can Rely On Today

- 分层 CI（PR / push / 手动集成 / E2E）与 lint、typecheck、单测、smoke 检查面齐全
- 结算并发通过行级锁与重试实现，权限与审计中间件覆盖到位
- 集成测试做了 xdist 并行安全隔离，前端类型与边界测试扎实
- 根级 AGENTS.md 与 Trellis 规范为代理提供明确的上下文路由
- 本地搭建文档、Docker 编排与 seed 脚本构成完整 onboarding 链

## What You Gain Next

- 改动验证: billing 核心链的数据库事务路径在合并前自动执行真实验收，变更后相关检查有确定路由 Smallest move: 把后端集成测试接入 PR 门禁，并为每个变更建立到受影响检查的映射
- 改动验证: 扣款失败可从日志回推触发点、边界与结果，诊断可关联且可验证 Smallest move: 为 billing 服务层失败路径补齐日志与稳定关联标识
- 改动验证: 数据语义变更在合并前经过可执行校验，downgrade 与业务计算一致 Smallest move: 为 Alembic 语义迁移添加独立测试与机械门禁



### Why these moves matter

### billing 核心链变更没有自动执行的集成验收
- Priority: Medium · Evidence: inspected and missing
- Reason: PR 门禁只运行 Mock 数据库的单元测试，集成测试依赖手动触发；窗口内 4 个候选片段无一存在针对最终变更的被审阅检查，两次变更均以未验证关闭。后果是行级锁、迁移升级与失败恢复路径在合并前从不自动执行。
- Expected Output:
  1. PR 门禁自动运行 billing 集成测试并保留失败产物
  2. 每个变更都有到受影响检查的确定路由

### billing 服务层失败路径没有任何日志输出
- Priority: Medium · Evidence: inspected and missing
- Reason: services/billing.py 约 1874 行、90 天变更密度最高，但全文件无 logger 调用；扣款失败、重试耗尽与批量部分失败只返回错误字符串，不留诊断痕迹。加上全链路无关联标识，运维只能从 500 响应回推代码。
- Expected Output:
  1. billing 服务关键失败路径存在可关联的 error 日志

### Alembic 语义迁移没有机械门禁与测试护栏
- Priority: Medium · Evidence: inspected and missing
- Reason: 新迁移把套餐超限单价的存储语义反转为 NULL 时自动计算，upgrade 与 downgrade 均改写数据；但该迁移无独立测试、无 schema 门禁、无 pre-commit 约束，且当前处于未提交状态。一旦与业务代码不同步合并，会造成结算金额静默漂移。
- Expected Output:
  1. 迁移 upgrade/downgrade 测试通过且与业务计算一致
  2. CI 存在迁移变更的门禁约束

### 日志与审计缺少跨边界关联标识
- Priority: Medium · Evidence: inspected and missing
- Reason: 中间件层只有鉴权与审计，没有 request id 或 trace id 注入；审计记录谁做了什么但无法关联具体调用、租户与事务边界。一次扣款失败只能按时间窗口人工拼凑日志，无法以稳定标识回查触发点到结果的完整链路。
- Expected Output:
  1. 请求链路具备稳定关联标识并写入响应头与日志

### 提交与收尾阶段反复出现执行失败
- Priority: Low · Evidence: not observed in this boundary
- Reason: 三个收尾片段连续落在提交、推送与归档边界：pre-commit 自动提交失败、分支完成需求未验证、归档与提交次序被用户重排，累计十一次执行失败。失败均无后果链证据，摩擦像来自环境或边界条件而非方向理解。
- Expected Output:
  1. 收尾流程单次执行无失败，pre-commit 失败可诊断

### 三个 Trellis Skills 为长文件且无渐进式引用
- Priority: Low · Evidence: static evidence only
- Reason: 确定性 lint 结果：trellis-update-spec（356 行）、trellis-brainstorm（200 行）、trellis-break-loop（188 行）均为线性长文件且无本地 Markdown 引用，维护性与渐进披露存在结构性风险。
- Expected Output:
  1. 三个 SKILL.md 通过渐进披露 lint 检查

### backend/app 深层源码没有包级上下文指令
- Priority: Low · Evidence: inspected and missing
- Reason: 项目 836 个追踪文件仅有一层嵌套 AGENTS.md，backend/app 97 个源文件与 backend/alembic 28 个文件只靠根级指令覆盖；代理定位 billing 服务层与路由拆分边界时只能依赖 grep 或 CodeGraph 搜索，缺少针对核心模块的上下文与风险路由。
- Expected Output:
  1. backend 核心模块存在包级上下文指令并路由到正确 owner

## Five Lifecycle Dimensions

| Dimension | What the evidence proves | Evidence boundary | Summary | Boundary / blocker |
| --- | --- | --- | --- | --- |
| 任务理解 | It is connected | connected, not seen in a task yet | 意图理解良好，用户以方向微调推进而非纠错。 | backend/app 深层源码缺少包级上下文指令。 |
| 可控执行 | It exists | static evidence only | 环境路由完整但无 doctor 语义，执行摩擦集中在收尾阶段。 | 缺少环境自检路由，收尾执行摩擦无诊断入口。 |
| 改动验证 | Inspected and missing | inspected and missing | 变更验证与故障诊断闭环在窗口内整体缺失。 | 相关验证、故障诊断与复验三环均无被观察证据。 |
| 可靠交付 | It exists | static evidence only | 交付机制存在但当前变更处于未验证的未提交状态。 | 当前分支未提交，收尾摩擦无后果链证据。 |
| 经验沉淀 | Not observed yet | not observed in this boundary | 重复需求不可判定，维护信号停留在静态层面。 | 独立重复需求与已运行学习回路均无被观察证据。 |

## The 15 Small Checks

| Dimension | Small check | What the evidence proves | Evidence boundary |
| --- | --- | --- | --- |
| 任务理解 | 意图与验收 | It is connected | connected, not seen in a task yet |
| 任务理解 | 相关上下文 | It is connected | connected, not seen in a task yet |
| 任务理解 | 范围边界 | It exists | static evidence only |
| 可控执行 | 可复现启动 | It exists | static evidence only |
| 可控执行 | 受支持操作 | It exists | static evidence only |
| 可控执行 | 权限边界 | It exists | static evidence only |
| 改动验证 | 相关验证 | Inspected and missing | inspected and missing |
| 改动验证 | 故障诊断与修复 | Inspected and missing | inspected and missing |
| 改动验证 | 修复后复验 | Not observed yet | not observed in this boundary |
| 可靠交付 | 交付验收 | It exists | static evidence only |
| 可靠交付 | 高风险审批 | Not needed for this task | not needed for this task |
| 可靠交付 | 回滚或恢复 | It exists | static evidence only |
| 经验沉淀 | 生命周期机会识别 | Not observed yet | not observed in this boundary |
| 经验沉淀 | 闭环工程化 | Not observed yet | not observed in this boundary |
| 经验沉淀 | 长期验证 | Not observed yet | not observed in this boundary |

## Evidence and Boundaries

- Episode coverage: 5 episodes, 3 edited, 0 closed, 0 repaired-and-passed
- Model: agent-work-loop-v4
- Session selection: all-eligible; 7 sessions analyzed of 7 eligible sessions; High confidence
- Delivery grades observed: not observed
- Source gaps: 13 个任务片段中 7 个无请求根，根扫描不完整，独立工作流需求无法判定; 摩擦到后果的链条未被观察，执行失败无法归因到具体机制
- Learning comparison: Needs a comparison; 0 declared intervention(s)
