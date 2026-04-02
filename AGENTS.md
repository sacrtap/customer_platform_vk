# AGENTS.md - 客户运营中台项目开发指南

## 📁 项目结构

```
customer_platform_vk/
├── backend/              # Python 后端 (Sanic + SQLAlchemy)
│   ├── app/              # 应用代码
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── routes/       # API 路由
│   │   ├── services/     # 业务逻辑
│   │   ├── middleware/   # 中间件
│   │   └── tasks/        # 定时任务
│   ├── tests/            # 测试代码
│   ├── migrations/       # Alembic 数据库迁移
│   └── scripts/          # 工具脚本
├── frontend/             # Vue3 前端
│   └── src/
│       ├── views/        # 页面组件
│       ├── components/   # 通用组件
│       ├── api/          # API 调用
│       └── stores/       # Pinia 状态管理
└── deploy/               # 部署配置
```

## 🛠️ 构建/测试/运行命令

### 后端 (Backend)

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行所有测试
python -m pytest

# 运行单个测试文件
python -m pytest tests/test_api.py -v

# 运行单个测试函数
python -m pytest tests/test_api.py::TestAuth::test_login_success -v

# 运行测试并生成覆盖率报告
python -m pytest --cov=app --cov-report=html

# 代码格式化
black app/ tests/

# 代码检查
flake8 app/ tests/

# 运行数据库迁移
python -m alembic upgrade head

# 创建新迁移
python -m alembic revision --autogenerate -m "description"

# 启动开发服务器
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

# 代码检查
npm run lint

# 代码格式化
npm run format
```

### 部署

```bash
# 生产环境部署
./deploy/scripts/deploy.sh

# 数据库备份
./deploy/scripts/backup.sh
```

## 📝 代码风格指南

### Python 后端

#### 导入规范
```python
# 顺序：标准库 → 第三方库 → 本地模块
import os
from sqlalchemy import select
from ..models.users import User
```

#### 类型注解
- 所有函数参数和返回值必须使用类型注解
- 使用 `Optional[T]` 表示可为空，使用 `Dict`, `List` 等泛型

```python
async def get_user_by_id(user_id: int) -> Optional[User]: ...
```

#### 命名约定
- **类**: PascalCase (`UserService`)
- **函数/方法**: snake_case (`get_user_by_id`)
- **常量**: UPPER_CASE (`MAX_FILE_SIZE`)

#### 错误处理
```python
try:
    result = await db.execute(query)
except OperationalError as e:
    logger.error(f"数据库操作失败：{str(e)}")
    raise
```

### TypeScript/JavaScript 前端

#### 导入规范
```typescript
import { ref } from 'vue'
import CustomerList from '@/components/CustomerList.vue'
import * as customerApi from '@/api/customers'
```

#### 类型注解
- 使用 TypeScript 严格模式，避免使用 `any`
- Props 和 emits 必须定义类型

```typescript
interface Customer { id: number; name: string }
const props = defineProps<{ customerId: number }>()
```

#### 命名约定
- **组件**: PascalCase (`CustomerList.vue`)
- **变量/函数**: camelCase (`fetchData`)
- **常量**: UPPER_CASE (`MAX_PAGE_SIZE`)

#### 错误处理
```typescript
try {
  const res = await customerApi.getCustomers(params)
} catch (err: any) {
  Message.error(err.message || '加载失败')
}
```

## ⚠️ 重要注意事项

1. **数据库操作**: 所有修改必须在事务中执行
2. **并发安全**: 余额扣款等关键操作必须使用行级锁
3. **安全验证**: Webhook 必须验证时间戳窗口和签名去重
4. **权限校验**: 所有 API 端点必须添加 `@auth_required` 装饰器
5. **日志记录**: 关键操作必须记录审计日志

## 📚 相关文档

- 设计文档：`docs/superpowers/specs/2026-04-01-customer-platform-design.md`
- 实现计划：`docs/superpowers/specs/2026-04-01-customer-platform-implementation-plan.md`
- 用户手册：`docs/user-manual.md`
- 项目总结：`docs/PROJECT_SUMMARY.md`

---

**最后更新**: 2026-04-03  
**项目状态**: Phase 0-7 完成，Critical Issues 已修复
