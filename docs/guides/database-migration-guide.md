# 数据库迁移指南

## 前置条件

1. 确保已安装 PostgreSQL 15+
2. 确保已安装 Python 依赖：
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

## 配置数据库连接

编辑 `backend/app/.env` 文件（或复制 `.env.example`）：

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/customer_platform

# JWT 配置
JWT_SECRET=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

## 创建数据库

```sql
-- 使用 psql 或 pgAdmin 执行
CREATE DATABASE customer_platform;
CREATE USER "user" WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE customer_platform TO "user";
```

## 运行数据库迁移

```bash
cd backend

# 查看当前迁移状态
python -m alembic history

# 运行所有迁移（创建所有表）
python -m alembic upgrade head

# 验证迁移结果
python -m alembic current
```

## 验证表结构

连接数据库查看创建的表：

```sql
\c customer_platform
\dt
```

应该看到以下 18 张表：
- users
- roles
- permissions
- user_roles
- role_permissions
- customers
- customer_profiles
- tags
- customer_tags
- profile_tags
- customer_balances
- recharge_records
- pricing_rules
- invoices
- invoice_items
- consumption_records
- daily_usage
- sync_logs
- audit_logs

## 创建初始数据（可选）

创建管理员账号：

```sql
INSERT INTO users (username, email, password_hash, name, is_system, is_active)
VALUES (
  'admin',
  'admin@example.com',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS3MebAJu',  -- admin123
  '系统管理员',
  true,
  true
);

INSERT INTO roles (name, description, is_system)
VALUES 
  ('系统管理员', '系统超级管理员', true),
  ('运营经理', '负责客户运营管理', false),
  ('销售人员', '负责客户开发', false);

-- 分配角色给管理员
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.username = 'admin' AND r.name = '系统管理员';
```

## 回滚迁移（如需）

```bash
# 回滚到上一个版本
python -m alembic downgrade -1

# 回滚到初始状态（删除所有表）
python -m alembic downgrade base
```

## 常见问题

### 1. 连接失败
检查数据库服务是否启动，用户名密码是否正确。

### 2. 权限不足
确保数据库用户对创建的表有完整权限。

### 3. 迁移冲突
如果有多个迁移文件，确保 `down_revision` 指向正确的前一个迁移。

### 4. 表已存在
如果是新数据库，确保之前没有手动创建过同名的表。

## 下一步

迁移完成后，可以启动后端服务：

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/health 验证服务是否正常。
