## Agent 体系

### Subagent 使用

OMP 通过 `task` tool 派遣 subagent 执行并行任务。Subagent 的配置见全局 `~/.omp/agent/config.yml` 的 `task.agentModelOverrides`。

### 项目自定义 Agents

本项目在 `config.yml` 中配置了以下专用 agent（用于领域特定任务）：

| Agent | 用途 |
|-------|------|
| `backend-architect` | 后端架构（Sanic/Python/PostgreSQL） |
| `frontend-developer` | 前端开发（Vue/TypeScript） |
| `api-tester` | API 测试专家 |
| `product-manager` | 产品需求分析 |
| `technical-writer` | 技术文档编写 |
| `ux-architect` | UX 架构设计 |

> **注意**：Agent 的行为由 `~/.omp/agent/config.yml` 中的模型映射控制。

### 使用原则

Subagent 的通用派遣规则以 `.omp/rules/superpowers.md` 的"子代理使用规范"和全局 `~/.omp/agent/SYSTEM.md` 为准；本文件只补充项目领域角色选择。

#### 领域角色选择

1. **后端架构、API、数据库、权限、事务** → `backend-architect`
2. **前端页面、Vue/TypeScript、组件拆分、UI 状态** → `frontend-developer`
3. **API 测试、接口契约、测试数据设计** → `api-tester`
4. **需求拆解、范围确认、验收口径** → `product-manager`
5. **技术文档、规则说明、README/API 文档** → `technical-writer`
6. **UX 架构、交互流程、样式系统** → `ux-architect`

#### 派遣边界

- 2 个以上独立模块、独立文件或可并行验证路径，优先按 `.omp/rules/superpowers.md` 使用 `dispatching-parallel-agents`。
- 同一文件的写入、共享状态迁移、顺序依赖修复必须串行；不要为了并行而拆分。
- 每个 subagent assignment 必须包含 `# Target`、`# Change`、`# Acceptance`；禁止派遣"随便看看"类无验收任务。
- 子代理不得运行项目级格式化、lint 或完整测试套件；主代理在最终阶段统一运行。
