# 客户运营中台硬规则

- **数据库事务**：所有修改操作必须在 `async with db_session.begin():` 块内执行
- **权限校验**：所有 API 端点必须添加 `@auth_required` 装饰器
- **测试覆盖率**：CI 要求测试覆盖率 ≥50%（`--cov-fail-under=50`）
- **Python 版本**：必须使用 Python 3.12.x，不支持 3.13+
- **并发安全**：余额扣款使用行级锁（`FOR UPDATE`）防止冲突
- **文件修改前必须先读取**：避免基于过时快照编辑

## 个人偏好
- **思考过程及会话内回复**：必须使用中文

## 开发环境
- **pre-commit hook 环境**：
  - 脚本必须使用 `$BACKEND_DIR/.venv/bin/python` 而非依赖 PATH
  - 环境配置问题必须在 24 小时内修复