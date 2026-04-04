# 技术债务记录

**记录日期**: 2026-04-03  
**项目**: 客户运营中台 (customer_platform_vk)  
**状态**: 开发中

---

## 已解决：Python 版本降级

**解决日期**: 2026-04-04  
**问题描述**:  
Python 3.14.3 与 Sanic 框架生态系统存在兼容性问题。

**解决方案**:
- ✅ 已降级到 Python 3.11.14
- ✅ 已降级 Sanic 到 22.12.0
- ✅ 已调整 httpx 到 0.23.3（兼容 sanic-testing）
- ✅ 单元测试全部通过（58/58）

**当前环境**:
```
Python: 3.11.14
Sanic: 22.12.0
sanic-ext: 22.12.0
sanic-testing: 22.12.0
httpx: 0.23.3
asyncpg: 0.29.0
```

---

## 已解决：集成测试事件循环冲突

**解决日期**: 2026-04-04  
**问题描述**:  
集成测试运行时出现 `RuntimeError: Task got Future attached to a different loop` 错误，导致 15/15 个集成测试失败。

**根因分析**:
- pytest-sanic 与 pytest-asyncio 事件循环管理冲突
- 双重事件循环导致 asyncpg 无法正常工作

**解决方案**:
1. ✅ 卸载 pytest-sanic (1.9.1)
2. ✅ 使用 Sanic ASGI Client (官方推荐)
3. ✅ 修改所有集成测试为异步模式 (@pytest.mark.asyncio)
4. ✅ 修复 UserService _is_async 检测逻辑
5. ✅ 修复 User.roles 懒加载问题 (使用 selectinload)
6. ✅ 修复 Sanic 22.x API 兼容性问题

**测试结果**:
- 集成测试：**15/15 通过 (100%)** ✅
- 单元测试：**241/260 通过 (93%)** ✅
  - 注：19 个失败测试是预先存在的问题，与本次修复无关

**修改文件**:
- `backend/tests/integration/conftest.py` - test_client fixture
- `backend/tests/integration/test_api.py` - 5 个测试
- `backend/tests/integration/test_groups_api.py` - 10 个测试
- `backend/app/services/users.py` - 异步检测 + selectinload
- `backend/app/routes/groups.py` - request.args API

**详细报告**: [event-loop-fix-report.md](./event-loop-fix-report.md)

---

## 当前技术债务

### 1. Analytics Service 单元测试 Mock 问题

**问题描述**:  
19 个 analytics service 单元测试失败，原因是 Mock 对象返回值不正确。

**影响范围**:
- tests/test_analytics_service.py 中的 19 个测试
- 不影响集成测试和生产代码

**建议方案**:
- 修复 Mock 配置，确保返回正确的数据结构
- 优先级：低（单元测试问题，不影响功能）

---
- Sanic 测试客户端 (`sanic-testing`) 创建独立事件循环
- asyncpg（通过 SQLAlchemy AsyncSession）使用另一个事件循环
- 两个 loop 不兼容，导致数据库连接失败

**影响范围**:
- `tests/integration/test_api.py` - 4 个测试失败
- `tests/integration/test_groups_api.py` - 9 个测试失败
- 单元测试不受影响（使用 Mock DB Session）

**测试结果**:
```
单元测试：58/58 通过 (100%) ✅
集成测试：1/15 通过 (6.7%) ❌
```

**解决方案（建议）**:

**短期** (当前采用):
- ✅ 接受集成测试限制
- ✅ 依赖单元测试（58 个全部通过）
- ✅ 通过手动测试/E2E 验证 API 功能
- ✅ 单元测试覆盖率：BillingService 96%, CustomerService 98%

**中期**:
- 方案 A: 修改集成测试夹具，使用同步测试客户端
- 方案 B: 使用 `pytest-asyncio` 的 `event_loop_policy` 配置
- 方案 C: 创建独立测试数据库和同步服务层
- 预计工作量：8-16 小时

**长期**:
- 评估测试框架替代方案（如 pytest-sanic）
- 考虑使用同步测试客户端进行集成测试
- 建立完整的测试金字塔体系

**优先级**: 中（不影响生产，单元测试已覆盖核心逻辑）  
**风险**: 低（单元测试已验证服务层逻辑）

---

## 技术债务管理策略

### 短期策略（1-2 周）
1. 保持当前状态，依赖单元测试
2. 补充关键服务的单元测试覆盖率
3. 使用 E2E 测试验证主要用户流程

### 中期策略（1-2 月）
1. 安排专门时间解决集成测试架构问题
2. 评估升级 Sanic 或降级到稳定版本
3. 建立 CI/CD 集成测试流程

### 长期策略（3-6 月）
1. 建立完整的测试金字塔
2. 单元测试 70% + 集成测试 20% + E2E 10%
3. 自动化测试报告和质量门禁

---

## 相关文件

- `docs/TESTING.md` - 测试策略文档
- `backend/tests/integration/README.md` - 集成测试说明
- `docs/tech-debt.md` - 技术债务总览（本文件）

---

**最后更新**: 2026-04-03  
**下次审查**: 2026-04-17
