---
name: runtime
description: "运行时环境配置和依赖管理：Python/Node.js 版本要求、包管理器和代码质量工具链配置"
ruleType: Model Request
---

## Runtime/Tooling Preferences

### 运行时要求

| 组件 | 版本 | 说明 |
|------|------|------|
| **Python** | **3.12.x** | ⚠️ **不支持 3.13+** |
| **Node.js** | **18+** | CI 使用 **22** |
| **PostgreSQL** | **18** | 主数据库 |
| **Redis** | **7+** | 缓存（后端必需） |

### 包管理器

- **后端**: `pip` + `requirements.txt`（≈40 个依赖）
- **前端**: `npm` + `package-lock.json`（≈20 个依赖）

### 代码质量工具链

| 工具 | 用途 | 配置 |
|------|------|------|
| **Ruff** | Python lint + format | `line-length=100`, `target-version=py312` |
| **ESLint** | TypeScript/Vue lint | `vue3-recommended` + `@typescript-eslint/recommended` |
| **Prettier** | 前端格式化 | `singleQuote`, `tabWidth=2`, `printWidth=100` |
| **pre-commit** | 提交前钩子 | ruff check + format + 完整验证脚本 |
