# Python 版本降级 - 快速执行指南

**创建日期**: 2026-04-04  
**优先级**: 🔴 高  
**预计时间**: 1-2 小时

---

## 📊 当前状态

| 项目 | 状态 |
|------|------|
| 当前 Python 版本 | 3.14.3 ❌ |
| 可用 Python 版本 | 3.9.x, 3.11.x, 3.14.3 |
| 目标 Python 版本 | 3.12.x (需安装) |
| 集成测试状态 | 全部失败 (兼容性问题) |

---

## 🚀 快速执行步骤

### 1️⃣ 安装 Python 3.12 (5 分钟)
```bash
brew install python@3.12
python3.12 --version  # 验证安装
```

### 2️⃣ 运行降级脚本 (15 分钟)
```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend
./scripts/downgrade-python.sh
```

### 3️⃣ 验证测试 (30 分钟)
```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行单元测试
python -m pytest tests/unit/ -v

# 运行集成测试
python -m pytest tests/integration/ -v

# 查看覆盖率
python -m pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### 4️⃣ 验证应用启动 (5 分钟)
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## ✅ 验证清单

- [ ] Python 3.12 安装成功
- [ ] 虚拟环境创建成功 (`python --version` 显示 3.12.x)
- [ ] 所有依赖安装成功（无错误）
- [ ] 单元测试全部通过
- [ ] 集成测试通过率 > 90%
- [ ] 应用可以正常启动
- [ ] API 端点响应正常

---

## ⚠️ 回滚方案

如果降级失败，执行以下命令回滚：

```bash
cd backend
rm -rf .venv
mv .venv.py3.14.backup .venv
source .venv/bin/activate
```

---

## 📋 交付物

| 文件 | 说明 |
|------|------|
| `docs/python-version-downgrade-plan.md` | 详细降级方案 |
| `backend/scripts/downgrade-python.sh` | 自动化降级脚本 |
| `backend/requirements.txt` | 已添加 Python 版本限制 |
| `docs/tech-debt.md` | 已更新技术债务记录 |

---

## 📞 问题支持

如遇到问题，请检查：
1. Homebrew 是否正常：`brew doctor`
2. Python 3.12 路径：`which python3.12`
3. 虚拟环境激活：`echo $VIRTUAL_ENV`

详细文档：`docs/python-version-downgrade-plan.md`
