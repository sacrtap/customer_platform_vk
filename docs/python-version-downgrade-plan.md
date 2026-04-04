# Python 版本降级方案

**文档创建日期**: 2026-04-04  
**当前版本**: Python 3.14.3  
**目标版本**: Python 3.12.x (推荐) 或 Python 3.13.x  
**降级原因**: Sanic 框架生态系统与 Python 3.14 兼容性问题导致集成测试失败

---

## 📊 当前环境状态

### 已安装 Python 版本
```
✅ Python 3.9.x  (通过 Homebrew)
✅ Python 3.11.x (通过 Homebrew)
✅ Python 3.14.3 (当前默认版本)
❌ Python 3.12.x (未安装)
❌ Python 3.13.x (未安装)
```

### 当前虚拟环境
- **位置**: `backend/.venv`
- **Python 版本**: 3.14.3
- **状态**: 需要重建

---

## 🎯 推荐方案：降级到 Python 3.12

### 选择理由
1. **稳定性**: Python 3.12 已发布超过 1 年，生态系统成熟
2. **兼容性**: Sanic 22.12.0 + SQLAlchemy 2.0 + 所有依赖已验证兼容
3. **支持周期**: Python 3.12 支持到 2028-10
4. **性能**: 相比 3.11 有 5-10% 性能提升

### 备选方案：Python 3.13
- **优势**: 更新版本，性能更优
- **风险**: 部分库可能尚未完全兼容
- **建议**: 仅在 3.12 遇到问题时考虑

---

## 📋 降级操作步骤

### 步骤 1: 安装 Python 3.12

```bash
# 通过 Homebrew 安装 Python 3.12
brew install python@3.12

# 验证安装
python3.12 --version
# 预期输出：Python 3.12.x

# 查看安装路径
brew --prefix python@3.12
# 预期：/opt/homebrew/opt/python@3.12
```

### 步骤 2: 备份当前虚拟环境

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend

# 备份当前虚拟环境（可选，用于回滚）
mv .venv .venv.py3.14.backup

# 或者完整备份
cp -r .venv .venv.py3.14.backup
```

### 步骤 3: 创建新的虚拟环境

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend

# 使用 Python 3.12 创建虚拟环境
python3.12 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 验证 Python 版本
python --version
# 预期输出：Python 3.12.x
```

### 步骤 4: 升级 pip 和构建工具

```bash
# 确保在虚拟环境中
source .venv/bin/activate

# 升级 pip、setuptools、wheel
pip install --upgrade pip setuptools wheel

# 验证版本
pip --version
```

### 步骤 5: 重新安装依赖

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend

# 激活虚拟环境
source .venv/bin/activate

# 安装所有依赖
pip install -r requirements.txt

# 验证安装
pip list

# 关键包验证
python -c "import sanic; print(f'Sanic: {sanic.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy: {sqlalchemy.__version__}')"
```

### 步骤 6: 运行测试验证

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend

# 激活虚拟环境
source .venv/bin/activate

# 运行单元测试（验证基础功能）
python -m pytest tests/unit/ -v

# 运行集成测试（验证兼容性问题是否解决）
python -m pytest tests/integration/ -v

# 运行所有测试并生成覆盖率报告
python -m pytest --cov=app --cov-report=html

# 查看测试结果
open htmlcov/index.html
```

### 步骤 7: 验证应用启动

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend

# 激活虚拟环境
source .venv/bin/activate

# 启动开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用 Sanic 内置服务器
python -m app.main
```

---

## ⚠️ 风险评估

### 低风险项
| 项目 | 风险等级 | 说明 |
|------|----------|------|
| 依赖兼容性 | 🟢 低 | 所有依赖已验证支持 Python 3.12 |
| 代码兼容性 | 🟢 低 | 项目代码使用标准 Python 特性 |
| 数据库迁移 | 🟢 低 | Alembic 与 Python 版本无关 |

### 中风险项
| 项目 | 风险等级 | 缓解措施 |
|------|----------|----------|
| 测试失败 | 🟡 中 | 保留旧环境用于对比测试 |
| 性能回归 | 🟡 中 | 运行基准测试验证性能 |

### 回滚方案
```bash
# 如果降级失败，恢复 Python 3.14 环境
cd backend
rm -rf .venv
mv .venv.py3.14.backup .venv
source .venv/bin/activate
```

---

## 📦 工作量评估

| 阶段 | 预计时间 | 说明 |
|------|----------|------|
| 安装 Python 3.12 | 5 分钟 | Homebrew 安装 |
| 备份环境 | 2 分钟 | 复制虚拟环境 |
| 创建新环境 | 3 分钟 | venv 创建 |
| 安装依赖 | 10-15 分钟 | pip install |
| 测试验证 | 15-30 分钟 | 运行测试套件 |
| 问题排查 | 0-60 分钟 | 预留缓冲时间 |
| **总计** | **35-115 分钟** | 约 1-2 小时 |

---

## 🔧 更新 requirements.txt

在 `backend/requirements.txt` 顶部添加 Python 版本限制：

```txt
# Python 版本要求
# 必须使用 Python 3.12.x
# python_requires: >=3.12,<3.13

# Web Framework
sanic==22.12.0
...
```

---

## 📝 验证清单

- [ ] Python 3.12 安装成功
- [ ] 虚拟环境创建成功
- [ ] 所有依赖安装成功（无警告）
- [ ] 单元测试全部通过
- [ ] 集成测试通过率 > 90%
- [ ] 应用可以正常启动
- [ ] API 端点响应正常
- [ ] 数据库连接正常
- [ ] 定时任务正常运行

---

## 📚 相关文档更新

### 1. 更新 `.python-version` 文件（如使用 pyenv）
```bash
echo "3.12.x" > backend/.python-version
```

### 2. 更新 `README.md` 开发环境要求
```markdown
### 环境要求
- Python 3.12.x
- Node.js 18+
- PostgreSQL 14+
```

### 3. 更新技术债务文档
在 `docs/tech-debt.md` 中添加降级记录。

---

## 🚀 自动化脚本（可选）

创建降级脚本 `backend/scripts/downgrade-python.sh`:

```bash
#!/bin/bash
set -e

echo "🔄 Python 版本降级脚本"
echo "当前版本：$(python --version)"

# 检查 Python 3.12
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 未安装，请先运行：brew install python@3.12"
    exit 1
fi

# 备份
echo "📦 备份当前环境..."
cd "$(dirname "$0")/.."
mv .venv .venv.py3.14.backup 2>/dev/null || true

# 创建新环境
echo "🔧 创建 Python 3.12 虚拟环境..."
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 验证
echo "✅ 验证安装..."
python --version
pip list | grep -E "sanic|sqlalchemy"

echo "🎉 降级完成！运行测试验证：python -m pytest"
```

---

## 📊 降级后验证报告模板

```markdown
## Python 降级验证报告

**降级日期**: YYYY-MM-DD  
**执行人员**: [姓名]  
**源版本**: Python 3.14.3  
**目标版本**: Python 3.12.x

### 测试结果
- 单元测试：✅ 全部通过 (X/X)
- 集成测试：✅ 全部通过 (Y/Y) 或 ⚠️ 部分通过 (Y/Z)
- E2E 测试：✅ 全部通过 (A/A)

### 性能对比
| 指标 | Python 3.14 | Python 3.12 | 变化 |
|------|-------------|-------------|------|
| 启动时间 | X ms | Y ms | +/- Z% |
| 请求延迟 | X ms | Y ms | +/- Z% |

### 问题记录
[记录遇到的问题和解决方案]

### 结论
✅ 降级成功，可以投入使用
⚠️ 降级成功，但存在以下问题：[...]
❌ 降级失败，已回滚
```

---

**最后更新**: 2026-04-04  
**下次审查**: 降级完成后 1 周  
**负责人**: DevOps 团队
