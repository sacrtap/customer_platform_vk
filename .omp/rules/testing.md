## Testing & QA

### 测试框架

#### 后端

- **框架**: pytest + pytest-asyncio (auto mode)
- **插件**: pytest-cov (覆盖率), pytest-xdist (并行), pytest-testmon (增量测试)
- **配置**: `pyproject.toml` 中 `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- **Fixture**: `conftest.py` 设置环境变量（DATABASE_URL/REDIS_URL/JWT_SECRET）

#### 前端

- **单元测试**: Vitest（jsdom 环境，globals 开启，istanbul 覆盖率）
- **E2E 测试**: Playwright（Chromium + Mobile Chrome，CI retries=2）
- **版本**: 见 `frontend/package.json` 和 `backend/pyproject.toml`

### 测试分层

| 层级 | 目录 | 说明 | 示例 |
|------|------|------|------|
| **单元测试** | `backend/tests/unit/` | 不依赖数据库，测试纯逻辑 | `test_billing_service.py`, `test_cache.py` |
| **集成测试** | `backend/tests/integration/` | 依赖真实数据库，测试 API 端点 | `test_customers_api.py`, `test_billing_api.py` |
| **服务层测试** | `backend/tests/services/` | 测试 Service 层业务逻辑 | `test_sync_task_service.py` |
| **E2E 测试** | `frontend/e2e/` | Playwright 端到端测试 | `test_login.spec.ts` |
| **性能测试** | `backend/tests/performance/` | 负载测试 | `test_api_load.py` |

### 覆盖率要求

- **CI 门禁**: 测试覆盖率 ≥50%（`--cov-fail-under=50`）
- **TDD 策略**: 按模块细化（见下表）

| 模块 | TDD 策略 |
|------|----------|
| 账号治理 | 核心权限逻辑 TDD，UI 组件 Tests-after |
| 客户信息管理 | 核心业务逻辑 TDD，导入导出 Tests-after |
| 结算管理 | **严格 TDD**（金额计算敏感） |
| 画像管理 | 等级/标签规则 TDD，页面 Tests-after |
| 客户分析 | 数据聚合逻辑 TDD，报表 UI Tests-after |
| 系统/通用 | Tests-after |

### 运行测试

```bash
# 后端完整测试
cd backend && make test

# 后端单元测试（最快）
cd backend && make test-fast

# 后端并行测试
cd backend && make test-parallel

# 后端覆盖率测试
cd backend && make test-cov

# 前端单元测试
cd frontend && npx vitest

# 前端 E2E 测试
cd frontend && npx playwright test

# 自动 E2E 测试（启停前后端）
./scripts/run-e2e-tests.sh
```

### CI/CD 流程

见 `.github/workflows/` 目录。

### 测试质量标准

- **测试真实行为**：测试必须测试真实行为，禁止测试内部实现细节
- **禁止测试间接层**：禁止为测试兼容性添加不必要的间接层
- **重构时测试**：重构时如需修改测试，必须说明原因并确认测试仍验证原始行为
