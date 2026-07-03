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

#### 选择策略

1. **领域知识任务** → 优先使用项目自定义 agent
   - 后端逻辑 → `backend-architect`
   - 前端页面 → `frontend-developer`
   - API 测试 → `api-tester`

2. **通用任务** → 使用 OMP 标准 subagent（如 `explore`, `oracle`, `quick_task`等）

3. **并行 I/O** → 优先使用 `eval` 的 `parallel()` 而非 `task`

#### 并行派遣规则

- **无依赖任务**：可并行派遣，最大化吞吐
- **有依赖任务**：需等待前置任务完成后再派遣
- **资源冲突**：避免对同一文件的并发写操作

详见全局配置：`~/.omp/agent/AGENTS.md`
