<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

<!-- CODEGRAPH_START -->
## CodeGraph — 本项目唯一代码索引工具

> **声明**: CodeGraph 是本项目的**唯一代码索引工具**。CatPaw 内置的 Codebase Index 已禁用，**不要使用 `@CODEBASE` mention**，不要依赖 CatPaw 远程嵌入索引。

### 使用优先级

1. **CodeGraph MCP 工具（首选）**: `codegraph_explore` 一次调用返回相关符号的完整源码 + 调用路径，覆盖大多数代码理解需求。
2. **CodeGraph Shell 命令（次选）**: `codegraph explore "<symbol names or question>"` 和 `codegraph node <symbol-or-file>` 输出同等信息，适用于 MCP 工具不可用时。
3. **grep_search（兜底）**: 仅用于精确字符串匹配或已知符号的快速定位。
4. **read_file（最后手段）**: 仅用于读取已知路径的文件内容。

### 何时使用 CodeGraph

- 理解代码结构和模块关系
- 定位符号定义（函数/类/变量）
- 分析调用路径和依赖关系
- 跨文件影响范围评估
- 回答 "X 在哪里定义/被谁调用/如何工作" 等问题

### 何时不需要 CodeGraph

- 已知确切文件路径的直接读取（用 `read_file`）
- 精确字符串/正则搜索（用 `grep_search`）
- 文件名查找（用 `glob_file_search`）

### Daemon 管理

- CodeGraph daemon idle 300s 后自动关闭，首次查询会自动启动
- 索引数据库位于 `.codegraph/codegraph.db`（已被 `.gitignore` 忽略，不入版本控制）
- 文件变更时自动增量同步（auto-sync），无需手动重建索引

### Fallback 策略

如果 `.codegraph/` 目录不存在或 daemon 未运行：
1. 先尝试 `codegraph explore` shell 命令（会自动初始化）
2. 如果命令不可用，回退到 `codebase_search` 语义搜索
3. 最后回退到 `grep_search` + `read_file`
<!-- CODEGRAPH_END -->
