.PHONY: test test-fast test-cov test-parallel test-unit test-integration test-all test-last-failed test-report

# 默认：分模块运行（先单元后集成）
test: test-all

# 最快：仅运行单元测试（不启动数据库）
test-fast:
	source .venv/bin/activate && pytest tests/unit/ -v --tb=short

# 并行：分模块并行运行（块内并行，块间顺序）
test-parallel:
	@echo "========== 运行单元测试（并行） =========="
	source .venv/bin/activate && pytest tests/unit/ -n auto --tb=short -q
	@echo ""
	@echo "========== 运行集成测试（串行，避免数据库冲突） =========="
	source .venv/bin/activate && pytest tests/integration/ --tb=short -q

# 完整分模块运行（详细输出）
test-all:
	@echo "========== 运行单元测试 =========="
	source .venv/bin/activate && pytest tests/unit/ -v --tb=short
	@echo ""
	@echo "========== 运行集成测试 =========="
	source .venv/bin/activate && pytest tests/integration/ -v --tb=short

# 只运行上次失败的测试
test-last-failed:
	source .venv/bin/activate && pytest tests/ --lf -v --tb=short

# 覆盖率：本地口径 = 单元 + 集成（排除 tests/e2e，与 CI nightly 的 50% 全量口径一致）。
# tests/e2e 依赖外部同步服务，本地跑会卡死；全量 E2E 由 e2e-full.yml 在 CI 执行。
#
# 三段式与 CI nightly（.github/workflows/pr-checks.yml 的 backend-integration-full）逐字对齐：
#   1) 单元测试生成 .coverage
#   2) 迁移测试单独串行跑（模块级 settings 缓存与 alembic 命令在 xdist 并行下相互污染）
#   3) 其余集成测试并行跑，--cov-append 合并，最终 --cov-fail-under=50 判定
# 本地只有单库，故集成段用 -n 1（CI 用 -n auto + gw0-gw3 四个并行库）。
test-cov:
	@echo "========== 1/3 单元测试（生成 .coverage） =========="
	source .venv/bin/activate && pytest tests/unit/ -q --tb=short --cov=app --cov-report=term-missing
	@echo ""
	@echo "========== 2/3 迁移测试（串行） =========="
	source .venv/bin/activate && pytest tests/integration/test_migrations.py -n 1 --timeout=120 \
		--tb=short --cov=app --cov-append --cov-report=term-missing
	@echo ""
	@echo "========== 3/3 其余集成测试（--cov-fail-under=50） =========="
	source .venv/bin/activate && pytest tests/integration/ --ignore=tests/integration/test_migrations.py \
		-n 1 --timeout=120 --tb=short --cov=app --cov-append --cov-report=term-missing \
		--cov-report=html --cov-fail-under=50

# 仅单元测试 + 覆盖率
test-unit:
	source .venv/bin/activate && pytest tests/unit/ -v --tb=short --cov=app --cov-report=term-missing

# 仅集成测试 + 覆盖率
test-integration:
	source .venv/bin/activate && pytest tests/integration/ -v --tb=short --cov=app --cov-report=term-missing

# 生成 HTML 覆盖率报告并在浏览器中打开
test-report: test-cov
	open htmlcov/index.html
