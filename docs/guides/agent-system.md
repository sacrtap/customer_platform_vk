# Agent 体系说明

本文档说明了客户运营中台平台的 Agent 使用原则。

---

## Subagent 选择策略

### 项目自定义 Agents（配置见 `~/.omp/agent/config.yml`）

| Agent | 用途 |
|-------|------|
| `backend-architect` | 后端架构（Sanic/Python/PostgreSQL） |
| `frontend-developer` | 前端开发（Vue/TypeScript） |
| `api-tester` | API 测试专家 |
| `product-manager` | 产品需求分析 |
| `technical-writer` | 技术文档编写 |
| `ux-architect` | UX 架构设计 |

### OMP 标准 Subagents

通过 `task` tool 调用的通用 subagent：

| Agent | 用途 |
|-------|------|
| `explore` | 只读代码探索 |
| `oracle` | 复杂问题推理/调试 |
| `quick_task` | 轻量机械任务 |
| `librarian` | 外部文档调研 |

### 选择规则

- **领域知识任务** → 优先使用项目自定义 agent
  - 后端逻辑 → `backend-architect`
  - 前端页面 → `frontend-developer`
  - API 测试 → `api-tester`

- **跨模块架构问题** → 使用 `oracle`

- **代码探索** → 使用 `explore`（READ-ONLY）

- **轻量操作** → 使用 `quick_task`

---

## 并行派遣规则

- **无依赖任务**：可并行派遣，最大化吞吐
- **有依赖任务**：需等待前置任务完成后再派遣
- **资源冲突**：避免对同一文件的并发写操作

详见全局配置：`~/.omp/agent/AGENTS.md`