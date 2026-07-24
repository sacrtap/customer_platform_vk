# Pre-commit 配置方案

**创建日期**: 2026-07-15
**状态**: 待确认
**目标**: 为项目提供完整的 pre-commit 配置方案

---

## 📊 当前配置现状

### 已有配置

**文件**: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        name: ruff check (linting)
        files: ^backend/
        types: [python]

      - id: ruff-format
        name: ruff format (formatting)
        files: ^backend/
        types: [python]

  - repo: local
    hooks:
      - id: pre-commit-check
        name: 提交前预验证脚本
        entry: bash -c 'cd "$(git rev-parse --show-toplevel)" && bash scripts/pre-commit-check.sh'
        language: system
        pass_filenames: false
        stages: [pre-commit]

> **最终选择**: 修正后的综合方案
> **确认时间**: 2026-07-15
> **大文件阈值**: 1000 KB (1 MB)

### 最终配置

```yaml
repos:
  # Universal hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-added-large-files
        args: ['--maxkb=1000']

  # Python backend - Ruff (matching project v0.14.0)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        name: Ruff check
        files: ^backend/
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
        name: Ruff format
        files: ^backend/

  # Python type checking (pre-push only, slow)
  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.380
    hooks:
      - id: pyright
        name: Pyright type check
        files: ^backend/
        args: [--project=pyrightconfig.json]
        stages: [pre-push]

  # Frontend - ESLint
  - repo: local
    hooks:
      - id: eslint
        name: ESLint (frontend)
        entry: bash -c 'cd frontend && npx eslint --ext .vue,.js,.ts,.tsx src/'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false

  # Frontend - Prettier (official mirror)
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.2.5
    hooks:
      - id: prettier
        name: Prettier format (frontend)
        files: ^frontend/
        types_or: [javascript, ts, vue, json, css]
        exclude: ^frontend/(dist|node_modules)/

  # Frontend - Type check (slow, pre-push)
  - repo: local
    hooks:
      - id: vue-tsc
        name: Vue TypeScript Check
        entry: bash -c 'cd frontend && npx vue-tsc --noEmit'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false
        stages: [pre-push]

  # Existing comprehensive check script
  - repo: local
    hooks:
      - id: pre-commit-check
        name: Full pre-commit verification
        entry: bash scripts/pre-commit-check.sh
        language: system
        pass_filenames: false
        stages: [pre-commit]
        verbose: true
```

### 现有脚本

**文件**: `scripts/pre-commit-check.sh`

功能：
- 后端检查：ruff lint/format、pytest 单元测试、pytest 集成测试
- 前端检查：vue-tsc 类型检查、eslint、vitest 单元测试

### 项目技术栈

| 层级 | 技术栈 | 工具 |
|------|--------|------|
| 后端 | Python 3.12 + Sanic | ruff, pytest, pyright |
| 前端 | Vue 3 + TypeScript | eslint, prettier, vue-tsc, vitest |
| 代码检查 | ruff (Python), eslint (前端) | 已配置 |
| 格式化 | ruff format (Python), prettier (前端) | 已配置 |
| 类型检查 | pyright (Python), vue-tsc (前端) | 部分配置 |
| 测试 | pytest (后端), vitest (前端) | 已配置 |

---

## 🎯 配置方案

### 方案 A：增强现有配置（推荐）

**特点**: 保留现有配置，补充通用 hooks 和前端格式化

```yaml
repos:
  # ==================== 通用 Hooks ====================
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
        name: 清理行尾空格
      - id: end-of-file-fixer
        name: 确保文件以换行符结尾
      - id: check-yaml
        name: 检查 YAML 语法
      - id: check-json
        name: 检查 JSON 语法
      - id: check-merge-conflict
        name: 检查合并冲突标记
      - id: detect-private-key
        name: 检测私钥文件
      - id: check-added-large-files
        name: 检查大文件
        args: ['--maxkb=1000']

  # ==================== Python 后端 ====================
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        name: ruff check (linting)
        files: ^backend/
        types: [python]
        args: [--fix, --exit-non-zero-on-fix]

      - id: ruff-format
        name: ruff format (formatting)
        files: ^backend/
        types: [python]

  # ==================== 前端 Vue/TypeScript ====================
  - repo: local
    hooks:
      - id: eslint
        name: eslint (前端代码检查)
        entry: bash -c 'cd frontend && npx eslint --ext .vue,.js,.jsx,.ts,.tsx src/'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false

      - id: prettier
        name: prettier (前端格式化)
        entry: bash -c 'cd frontend && npx prettier --write "src/**/*.{vue,js,ts,css}"'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue, css]
        pass_filenames: false

      - id: vue-tsc
        name: vue-tsc (类型检查)
        entry: bash -c 'cd frontend && npx vue-tsc --noEmit'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false

  # ==================== 测试验证（可选） ====================
  - repo: local
    hooks:
      - id: backend-tests
        name: 后端单元测试
        entry: bash -c 'cd backend && python -m pytest tests/unit/ -x --tb=short -q'
        language: system
        files: ^backend/
        types: [python]
        pass_filenames: false
        stages: [pre-push]  # 改为 pre-push 避免每次提交都运行

      - id: frontend-tests
        name: 前端单元测试
        entry: bash -c 'cd frontend && npm run test:unit -- --run'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false
        stages: [pre-push]  # 改为 pre-push 避免每次提交都运行
```

**优势**:
- ✅ 保留现有 ruff 配置，兼容性好
- ✅ 添加通用 hooks 防止常见问题
- ✅ 前端 eslint/prettier/vue-tsc 集成
- ✅ 测试移到 pre-push 阶段，避免阻塞提交
- ✅ 与现有 `scripts/pre-commit-check.sh` 互补

**预计提交时间**: 5-10 秒

---

### 方案 B：精简配置（性能优先）

**特点**: 追求更快的提交速度，精简配置

```yaml
repos:
  # 通用 Hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict
      - id: detect-private-key

  # Python 后端
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        files: ^backend/
        types: [python]
        args: [--fix]
      - id: ruff-format
        files: ^backend/
        types: [python]

  # 前端（仅格式化）
  - repo: local
    hooks:
      - id: prettier
        name: prettier
        entry: bash -c 'cd frontend && npx prettier --write "src/**/*.{vue,js,ts,css}"'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue, css]
        pass_filenames: false
```

**优势**:
- ⚡ 提交速度更快（跳过类型检查和测试）
- ⚡ 依赖更少，维护简单
- ⚡ 适合快速迭代开发

**劣势**:
- ❌ 缺少类型检查（vue-tsc）
- ❌ 缺少 eslint 检查
- ❌ 测试需要手动运行

**预计提交时间**: 2-3 秒

---

### 方案 C：完整配置（严格模式）

**特点**: 最严格的代码质量保障

```yaml
repos:
  # 通用 Hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-case-conflict
      - id: check-docstring-first
      - id: debug-statements

  # Python 后端
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        files: ^backend/
        types: [python]
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
        files: ^backend/
        types: [python]

  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.350
    hooks:
      - id: pyright
        name: pyright (类型检查)
        files: ^backend/
        types: [python]

  # 前端
  - repo: local
    hooks:
      - id: eslint
        name: eslint
        entry: bash -c 'cd frontend && npx eslint --ext .vue,.js,.jsx,.ts,.tsx src/'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false

      - id: prettier
        name: prettier
        entry: bash -c 'cd frontend && npx prettier --check "src/**/*.{vue,js,ts,css}"'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue, css]
        pass_filenames: false

      - id: vue-tsc
        name: vue-tsc
        entry: bash -c 'cd frontend && npx vue-tsc --noEmit'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false

  # 测试（pre-commit 阶段）
  - repo: local
    hooks:
      - id: backend-tests
        name: 后端单元测试
        entry: bash -c 'cd backend && python -m pytest tests/unit/ -x --tb=short -q'
        language: system
        files: ^backend/
        types: [python]
        pass_filenames: false

      - id: frontend-tests
        name: 前端单元测试
        entry: bash -c 'cd frontend && npm run test:unit -- --run'
        language: system
        files: ^frontend/
        types_or: [javascript, ts, vue]
        pass_filenames: false
```

**优势**:
- 🔒 最严格的代码质量保障
- 🔒 包含类型检查（pyright + vue-tsc）
- 🔒 每次提交都运行测试

**劣势**:
- 🐢 提交速度最慢（可能需要 30-60 秒）
- 🐢 依赖较多，维护复杂

**预计提交时间**: 30-60 秒

---

## 🔧 Hook 详细说明

### 通用 Hooks

| Hook | 作用 | 适用场景 |
|------|------|----------|
| `trailing-whitespace` | 清理行尾空格 | 所有文本文件 |
| `end-of-file-fixer` | 确保文件以换行符结尾 | 所有文本文件 |
| `check-yaml` | 检查 YAML 语法 | CI/CD 配置文件 |
| `check-json` | 检查 JSON 语法 | package.json 等 |
| `check-merge-conflict` | 检查合并冲突标记 | 所有文件 |
| `detect-private-key` | 检测私钥文件 | 防止泄露敏感信息 |
| `check-added-large-files` | 检查大文件 | 防止提交大文件（>1MB） |
| `check-case-conflict` | 检查大小写冲突 | 跨平台兼容性 |
| `check-docstring-first` | 检查 docstring 位置 | Python 文件 |
| `debug-statements` | 检查调试语句 | Python 文件 |

### Python 后端 Hooks

| Hook | 作用 | 配置 |
|------|------|------|
| `ruff` | 代码检查（linting） | 自动修复，非零退出 |
| `ruff-format` | 代码格式化 | 统一代码风格 |
| `pyright` | 类型检查 | 静态类型分析（方案 C） |

### 前端 Hooks

| Hook | 作用 | 配置 |
|------|------|------|
| `eslint` | 代码检查 | Vue/JS/TS 文件 |
| `prettier` | 代码格式化 | Vue/JS/TS/CSS 文件 |
| `vue-tsc` | 类型检查 | Vue/TS 文件 |

### 测试 Hooks

| Hook | 作用 | 阶段 |
|------|------|------|
| `backend-tests` | 后端单元测试 | pre-push（方案 A）/ pre-commit（方案 C） |
| `frontend-tests` | 前端单元测试 | pre-push（方案 A）/ pre-commit（方案 C） |

---

## 📝 安装和使用

### 1. 安装 pre-commit

```bash
# 使用 pip 安装
pip install pre-commit

# 验证安装
pre-commit --version
```

### 2. 安装 Git Hooks

```bash
# 安装 pre-commit hooks
pre-commit install

# 安装 pre-push hooks（如果需要运行测试）
pre-commit install --hook-type pre-push
```

### 3. 常用命令

```bash
# 手动运行所有 hooks（所有文件）
pre-commit run --all-files

# 仅运行特定 hook
pre-commit run ruff --all-files
pre-commit run eslint --all-files
pre-commit run prettier --all-files

# 运行特定文件的 hooks
pre-commit run --files backend/app/main.py

# 更新 hooks 版本
pre-commit autoupdate

# 查看 hooks 状态
pre-commit gc

# 卸载 hooks
pre-commit uninstall
```

### 4. CI/CD 集成

在 GitHub Actions 中添加：

```yaml
name: Pre-commit

on: [push, pull_request]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - uses: pre-commit/action@v3.0.0
```

---

## ⚠️ 注意事项

### 1. Python 版本

- 项目要求 Python 3.12.x
- 确保 pre-commit 环境使用相同版本
- 检查：`python --version`

### 2. 前端依赖

- 确保 `node_modules` 已安装
- 运行：`cd frontend && npm install`
- 建议在 CI 中也运行 pre-commit 检查

### 3. 与现有脚本的关系

- 现有 `scripts/pre-commit-check.sh` 可以作为补充
- 如果选择方案 A，可以保留该脚本用于完整检查
- 如果选择方案 B/C，可以考虑移除该脚本

### 4. 性能影响

| 方案 | 预计提交时间 | 适用场景 |
|------|--------------|----------|
| 方案 A | 5-10 秒 | 平衡速度和质量（推荐） |
| 方案 B | 2-3 秒 | 快速迭代开发 |
| 方案 C | 30-60 秒 | 严格质量保障 |

### 5. 文件过滤

可以通过 `files` 和 `exclude` 配置过滤文件：

```yaml
# 仅检查特定目录
files: ^backend/

# 排除特定文件
exclude: |
  (?x)^(
    backend/alembic/versions/.*|
    frontend/dist/.*|
    .*\.min\.js$
  )$
```

### 6. 跳过 Hooks

临时跳过 hooks（不推荐）：

```bash
git commit --no-verify -m "message"
```

---

## 🎯 推荐方案

### 推荐：方案 A（增强现有配置）

**理由**:

1. ✅ **保留现有配置**：迁移成本低，不影响现有工作流
2. ✅ **添加通用 hooks**：防止常见问题（空格、YAML 语法、私钥泄露）
3. ✅ **前端集成**：eslint/prettier/vue-tsc 完整集成
4. ✅ **性能平衡**：测试移到 pre-push，平衡速度和质量
5. ✅ **互补性强**：与现有 `scripts/pre-commit-check.sh` 互补

### 备选：方案 B（精简配置）

**适用场景**:
- 快速迭代开发阶段
- 团队偏好手动运行测试
- 追求最快的提交速度

### 备选：方案 C（完整配置）

**适用场景**:
- 生产环境代码提交
- 严格的代码质量要求
- 团队规模较大，需要严格规范

---

## 📋 实施步骤

### 步骤 1：选择方案

确认采用哪个方案（A/B/C）

### 步骤 2：更新配置文件

根据选择的方案更新 `.pre-commit-config.yaml`

### 步骤 3：安装 Hooks

```bash
# 安装 pre-commit hooks
pre-commit install

# 安装 pre-push hooks（方案 A/C）
pre-commit install --hook-type pre-push
```

### 步骤 4：验证配置

```bash
# 运行所有 hooks
pre-commit run --all-files

# 检查是否有错误
# 如果有错误，修复后重新提交
```

### 步骤 5：提交测试

```bash
# 创建一个测试提交
git add .
git commit -m "test: pre-commit configuration"

# 观察 hooks 运行情况
# 确认所有检查通过
```

### 步骤 6：团队同步

```bash
# 将配置提交到仓库
git push

# 团队成员安装 hooks
git pull
pre-commit install
pre-commit install --hook-type pre-push  # 方案 A/C
```

---

## 🔍 故障排查

### 问题 1：Hook 运行失败

**症状**: `pre-commit run` 报错

**解决**:
```bash
# 查看错误日志
pre-commit run --all-files

# 检查依赖是否安装
pip list | grep pre-commit
cd frontend && npm list eslint prettier

# 重新安装 hooks
pre-commit uninstall
pre-commit install
```

### 问题 2：Python 版本不匹配

**症状**: ruff 或其他 Python hooks 报错

**解决**:
```bash
# 检查 Python 版本
python --version

# 确保使用 Python 3.12.x
# 如果使用 pyenv
pyenv local 3.12.x
```

### 问题 3：前端依赖未安装

**症状**: eslint/prettier/vue-tsc 报错

**解决**:
```bash
cd frontend
npm install
```

### 问题 4：Hook 运行缓慢

**症状**: 提交时间过长

**解决**:
- 考虑切换到方案 B（精简配置）
- 将测试移到 pre-push 阶段
- 使用 `files` 过滤不必要的文件

---

## 📚 参考资料

- [Pre-commit 官方文档](https://pre-commit.com/)
- [Pre-commit Hooks 列表](https://pre-commit.com/hooks.html)
- [Ruff 文档](https://docs.astral.sh/ruff/)
- [ESLint 文档](https://eslint.org/)
- [Prettier 文档](https://prettier.io/)
- [Vue TSC 文档](https://github.com/vuejs/language-tools)

---

## 📞 支持

如有问题，请：
1. 查看本文档的故障排查部分
2. 检查 pre-commit 官方文档
3. 联系团队技术负责人

---

**文档版本**: v1.0
**最后更新**: 2026-07-15
**维护者**: 开发团队
