# CI 错误修复计划

**创建日期**: 2026-05-07
**优先级**: 高（CI阻塞主分支部署）
**影响范围**: 所有工作流（CI、Integration Tests、Deploy）

---

## 问题汇总

| 序号 | 问题分类 | 影响Job数 | 严重程度 |
|------|---------|-----------|---------|
| 1 | Python代码格式（black） | 1 | 中 |
| 2 | TypeScript类型错误 | 1 | 高 |
| 3 | Alembic异步引擎配置 | 3 | 高 |
| 4 | 单元测试数据库依赖 | 1 | 中 |
| 5 | Bandit安全扫描警告 | 1 | 低 |
| 6 | npm依赖漏洞 | 1 | 中 |

---

## Task 1: 修复Python代码格式（black）

### 问题描述
CI日志：`6 files would be reformatted, 88 files would be left unchanged`

### 根因分析
最近提交可能跳过了black格式化，或者合并引入了格式不一致的代码。

### 修复步骤
```bash
cd backend
black app/ tests/
```

### 验证
```bash
black app/ tests/ --check --diff
```
预期输出：`All done! ✨ 🍰 ✨ X files would be left unchanged.`

---

## Task 2: 修复TypeScript类型错误

### 问题描述
vue-tsc报告4个编译错误：

| 文件 | 行号 | 错误类型 | 说明 |
|------|------|---------|------|
| `ConsumeLevelProgress.vue` | 62 | TS6196 | `_ConsumeLevel`类型声明但未使用 |
| `BalanceTrendChart.vue` | 52 | TS2339 | `axisValue`不存在于`CallbackDataParams`类型 |
| `Home.vue` | 415 | TS18046 | `res`类型为`unknown` |
| `Index.vue` | 347 | TS2345 | 类型不匹配：`roles`应为`string[]`但映射为`{id: number}[]` |

### 修复步骤

#### 2.1 ConsumeLevelProgress.vue - 删除未使用类型
```typescript
// 删除第62行
// type _ConsumeLevel = typeof CONSUME_LEVELS[number]['value']
```

#### 2.2 BalanceTrendChart.vue - 修复axisValue类型
```typescript
// 第52行改为：
let result = `${(arr[0] as CallbackDataParams).axisValueLabel}<br/>`
// 或使用可选链：
let result = `${(arr[0] as any).axisValue ?? ''}<br/>`
```

#### 2.3 Home.vue - 添加类型断言
```typescript
// 第415行改为：
const res = await getDashboardChartData({ months: 12 })
await nextTick()
await initChart(
  (res as any).data.consumption_trend as Array<{ period: string; total_amount: number }>
)
```

#### 2.4 Index.vue - 修复role_ids类型
```typescript
// 第347行，需要查看roles的实际类型定义
// 如果roles是string[]，改为：
role_ids: item.roles || [],
// 如果roles是{id: number}[]，需要更新User类型定义
```

### 验证
```bash
cd frontend
npx vue-tsc --noEmit
```
预期输出：无错误

---

## Task 3: 修复Alembic异步引擎配置

### 问题描述
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

### 根因分析
`alembic/env.py`使用同步的`engine_from_config`，但`settings.database_url`配置的是异步连接串（`postgresql+asyncpg://`）。Alembic不支持异步引擎。

### 修复步骤

修改`backend/alembic/env.py`：

```python
# 第34-44行改为：
def run_migrations_online() -> None:
    """在线模式 - 执行迁移到数据库"""
    # 使用同步引擎（Alembic不支持asyncpg）
    from sqlalchemy import create_engine

    # 将asyncpg URL转换为psycopg2 URL
    sync_url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')

    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### 验证
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://test_user:test_password@localhost:5432/test_db" \
python -m alembic upgrade head
```
预期输出：无错误，迁移成功

---

## Task 4: 修复单元测试数据库依赖

### 问题描述
```
OSError: Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432, 0, 0)
```
`tests/unit/test_audit_helpers.py`尝试连接数据库，但单元测试不应依赖外部数据库。

### 根因分析
`test_audit_helpers.py`的fixture创建了真实的数据库引擎，但Integration Tests工作流中的`unit-test` job没有启动PostgreSQL服务。

### 修复方案

#### 方案A：Mock数据库连接（推荐）
修改`tests/unit/test_audit_helpers.py`，使用mock替代真实数据库连接。

#### 方案B：添加数据库服务
在`integration-tests.yml`的`unit-test` job中添加PostgreSQL服务。

**推荐方案A**，因为单元测试应该独立于外部服务。

### 验证
```bash
cd backend
pytest tests/unit/ -v --tb=short
```
预期输出：所有测试通过

---

## Task 5: 修复Bandit安全扫描

### 问题描述
Bandit退出码1表示发现安全问题。需要查看具体报告。

### 修复步骤
1. 下载并分析报告：
```bash
# 查看bandit报告
cat bandit-report.json | python3 -m json.tool
```

2. 根据报告修复：
- 如果是误报，添加`# nosec`注释
- 如果是真实问题，修复代码

### 验证
```bash
bandit -r backend/app/ -f txt -ll
```
预期输出：无HIGH/CRITICAL级别问题

---

## Task 6: 修复npm依赖漏洞

### 问题描述
```
11 vulnerabilities (4 moderate, 7 high)
```

### 修复步骤
```bash
cd frontend
npm audit fix
```

如果`npm audit fix`无法修复所有问题：
```bash
# 查看具体漏洞
npm audit

# 手动升级有问题的依赖
npm install <package>@latest
```

### 验证
```bash
npm audit --audit-level=high
```
预期输出：无high/critical级别漏洞

---

## 执行顺序建议

1. **Task 1** (black格式) - 最快，1分钟
2. **Task 2** (TypeScript错误) - 需要仔细修改类型，15分钟
3. **Task 3** (Alembic配置) - 关键修复，影响多个job，10分钟
4. **Task 4** (单元测试依赖) - 需要重构测试fixture，20分钟
5. **Task 5** (Bandit扫描) - 取决于具体问题，10-30分钟
6. **Task 6** (npm漏洞) - 取决于依赖兼容性，15分钟

**总预估时间**: 70-90分钟

---

## 验证策略

所有修复完成后，本地验证：
```bash
# 后端
cd backend
black app/ tests/ --check
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
pytest tests/ --cov=app --cov-fail-under=50

# 前端
cd frontend
npm run lint
npx vue-tsc --noEmit
npm run build
```

然后推送触发CI验证。
