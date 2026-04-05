# Uvicorn 启动命令迁移文档

**更新日期**: 2026-04-05  
**迁移类型**: 后端服务器启动命令标准化

---

## 📋 变更概述

将后端开发服务器的启动命令从 `python -m sanic` 统一迁移至 `python -m uvicorn`。

### 变更前后对比

| 项目 | 变更前 | 变更后 |
|------|--------|--------|
| **启动命令** | `python -m sanic app.main:app` | `python -m uvicorn app.main:app` |
| **服务器类型** | Sanic 内置服务器 | 独立 ASGI 服务器 |
| **适用场景** | 仅 Sanic 框架 | 所有 ASGI 框架 |

---

## 🎯 迁移原因

### 1. 生产环境推荐
- **uvicorn** 是生产环境推荐的 ASGI 服务器
- 性能更优，社区支持更成熟
- 与 gunicorn 配合有更好的多进程方案

### 2. 框架统一性
- 如果团队同时使用 FastAPI 和 Sanic，uvicorn 提供统一的启动方式
- 更符合 ASGI 规范，便于未来框架切换

### 3. 标准化
- AGENTS.md 中已配置 uvicorn 作为标准启动方式
- 保持文档与实际操作的一致性

---

## 🔧 依赖安装

### 方式 1: 单独安装
```bash
cd backend
source .venv/bin/activate
pip install uvicorn==0.25.0
```

### 方式 2: 更新 requirements.txt (推荐)
```bash
# requirements.txt 已添加 uvicorn==0.25.0
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 验证安装
```bash
python -c "import uvicorn; print(f'Uvicorn 版本：{uvicorn.__version__}')"
# 输出：Uvicorn 版本：0.25.0
```

## 📝 已更新文件

### 1. README.md
```diff
- python -m sanic app.main:app --reload --host 0.0.0.0 --port 8000
+ python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

- poetry run python -m sanic app.main:app --reload
+ poetry run python -m uvicorn app.main:app --reload
```

### 2. scripts/run-e2e-tests.sh
```diff
- echo "  启动 Sanic 服务器 (端口 8000)..."
- python -m sanic app.main:app --host=0.0.0.0 --port=8000 > "$BACKEND_LOG" 2>&1 &
+ echo "  启动 Uvicorn 服务器 (端口 8000)..."
+ python -m uvicorn app.main:app --host=0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
```

### 3. AGENTS.md
- 已使用 uvicorn 命令（无需修改）

---

## 🔧 技术细节

### ASGI 应用格式
```bash
# 标准 ASGI 格式：模块路径：应用变量
python -m uvicorn app.main:app
#                    │      │
#                    │      └─ Sanic 应用实例
#                    └─ 模块路径 (backend/app/main.py)
```

### 等效性说明
对于 Sanic 应用，以下两种启动方式功能基本等价：

```bash
# 方式 1: uvicorn (推荐)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式 2: sanic 内置
python -m sanic app.main:app --host=0.0.0.0 --port 8000
```

### 热重载支持
两种方式都支持开发模式热重载：
- uvicorn: `--reload` 标志
- sanic: 自动检测文件变化

---

## ✅ 验证步骤

### 0. 安装依赖
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### 1. 基础启动测试
```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 健康检查
```bash
curl http://localhost:8000/health
# 预期输出：{"status": "healthy"}
```

### 3. E2E 测试
```bash
./scripts/run-e2e-tests.sh
# 验证测试脚本能正常启动后端服务
```

---

## 📚 相关资源

- [Uvicorn 官方文档](https://www.uvicorn.org/)
- [ASGI 规范](https://asgi.readthedocs.io/)
- [Sanic ASGI 模式](https://sanic.dev/en/guide/running/runner.html#asgi-mode)

---

## 🔄 回滚方案

如需回滚至 sanic 启动方式，修改以下命令：

```bash
# README.md
python -m sanic app.main:app --reload --host 0.0.0.0 --port 8000

# scripts/run-e2e-tests.sh
python -m sanic app.main:app --host=0.0.0.0 --port=8000
```

---

**迁移状态**: ✅ 完成  
**影响范围**: 开发环境启动命令  
**向后兼容**: 是（sanic 命令仍可工作）

### 已验证
- ✅ Uvicorn 0.25.0 安装成功
- ✅ Sanic 应用可正常加载
- ✅ 启动命令语法正确
