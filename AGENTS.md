# AGENTS.md - 客户运营中台项目开发指南

## 🤖 Agent 工作指南

### 语言与沟通
- **思考过程**: 使用中文表述
- **回答语言**: 中文回复
- **文档语言**: 所有生成文档使用中文，保存到 `docs/` 目录下的合理位置
- **API/代码文档**: 优先使用 Context7 查询

### Context-Mode 强制规则 ⚠️
本项目使用 context-mode MCP 工具，**必须遵守**以下规则：

| 禁止操作 | 替代方案 |
|---------|---------|
| `curl` / `wget` 命令 | `context-mode_ctx_fetch_and_index(url, source)` |
| Shell 中 HTTP 请求 | `context-mode_ctx_execute(language, code)` |
| 大输出 Shell 命令 | `context-mode_ctx_batch_execute(commands, queries)` |
| 分析性文件读取 | `context-mode_ctx_execute_file(path, language, code)` |

**工具优先级**: GATHER → FOLLOW-UP → PROCESSING → WEB → INDEX

---

## 📁 项目结构

```
customer_platform_vk/
├── backend/              # Python 后端 (Sanic + SQLAlchemy)
│   ├── app/              # 应用代码 (models, routes, services, middleware, tasks)
│   ├── tests/            # 测试代码 (unit, integration, performance)
│   ├── alembic/          # 数据库迁移
│   └── scripts/          # 工具脚本
├── frontend/             # Vue3 + TypeScript 前端
│   └── src/              # views, components, api, stores
├── deploy/               # 部署配置 (Docker, scripts, monitoring)
└── docs/                 # 项目文档
```

---

## 🛠️ 构建/测试/运行命令

### 后端 (Backend)

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# ===== 测试命令 =====
# 运行单个测试函数 (最常用)
python -m pytest tests/unit/test_auth_service.py::TestAuthService::test_login_success -v

# 运行单个测试文件
python -m pytest tests/integration/test_api.py -v

# 运行所有测试
python -m pytest

# 运行测试并生成覆盖率报告
python -m pytest --cov=app --cov-report=html

# ===== 代码质量 =====
black app/ tests/              # 格式化
flake8 app/ tests/             # 代码检查

# ===== 数据库 =====
python -m alembic upgrade head                    # 运行迁移
python -m alembic revision --autogenerate -m "desc"  # 创建迁移

# ===== 开发服务器 =====
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端 (Frontend)

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 类型检查
npx vue-tsc --noEmit

# 代码检查与格式化
npm run lint
npm run format
```

### 部署 (Deploy)

```bash
# Docker Compose 部署 (推荐)
./deploy/scripts/deploy.sh
./deploy/scripts/deploy.sh --test-data      # 创建测试数据
./deploy/scripts/deploy.sh --skip-build     # 跳过构建

# 本地 PostgreSQL 部署 (macOS)
./deploy/scripts/local-deploy.sh

# 验证部署
./deploy/scripts/verify-deployment.sh

# 数据库备份
./deploy/scripts/backup.sh
```

---

## 📝 代码风格指南

### Python 后端

**导入规范**: 标准库 → 第三方库 → 本地模块
```python
import os
from sqlalchemy import select
from ..models.users import User
```

**类型注解**: 所有函数必须使用类型注解
```python
async def get_user_by_id(user_id: int) -> Optional[User]:
```

**命名约定**: 类 PascalCase | 函数 snake_case | 常量 UPPER_CASE

**错误处理**: 记录日志后重新抛出
```python
try:
    result = await db.execute(query)
except OperationalError as e:
    logger.error(f"数据库操作失败：{str(e)}")
    raise
```

### TypeScript 前端

**导入规范**:
```typescript
import { ref } from 'vue'
import CustomerList from '@/components/CustomerList.vue'
```

**类型定义**: 避免 `any`, Props/Emits 必须定义类型
```typescript
interface Customer { id: number; name: string }
const props = defineProps<{ customerId: number }>()
```

**命名约定**: 组件 PascalCase | 变量 camelCase | 常量 UPPER_CASE

---

## ⚠️ 关键安全要求

1. **数据库事务**: 所有修改操作必须在事务中执行
2. **并发安全**: 余额扣款使用行级锁 (`FOR UPDATE`)
3. **Webhook 验证**: 验证时间戳窗口 + 签名去重
4. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
5. **审计日志**: 关键操作必须记录到 `audit_logs` 表

---

## 📚 核心文档

| 文档 | 路径 |
|------|------|
| 设计文档 | `docs/superpowers/specs/2026-04-01-customer-platform-design.md` |
| 部署指南 | `deploy/README.md` |
| 部署一致性报告 | `docs/DEPLOY_CONSISTENCY_REPORT.md` |
| 测试数据库配置 | `docs/testing/test-database-setup.md` |

---

**最后更新**: 2026-04-04  
**项目状态**: Phase 0-7 完成，Docker 部署配置已完善  
**Python 版本**: 3.12 (Sanic 兼容) | **PostgreSQL**: 18
