.PHONY: test test-fast test-cov test-parallel test-unit test-integration test-all test-last-failed test-report

# 默认：分模块运行（先单元后集成）
test: test-all

# 最快：仅运行单元测试（不启动数据库）
test-fast:
	source .venv/bin/activate && python -m pytest tests/unit/ -v --tb=short

# 并行：分模块并行运行（块内并行，块间顺序）
test-parallel:
	@echo "========== 运行单元测试 =========="
	source .venv/bin/activate && python -m pytest tests/unit/ -n auto --tb=short -q
	@echo ""
	@echo "========== 运行集成测试 =========="
	source .venv/bin/activate && python -m pytest tests/integration/ -n auto --tb=short -q

# 完整分模块运行（详细输出）
test-all:
	@echo "========== 运行单元测试 =========="
	source .venv/bin/activate && python -m pytest tests/unit/ -v --tb=short
	@echo ""
	@echo "========== 运行集成测试 =========="
	source .venv/bin/activate && python -m pytest tests/integration/ -v --tb=short

# 只运行上次失败的测试
test-last-failed:
	source .venv/bin/activate && python -m pytest tests/ --lf -v --tb=short

# 覆盖率：运行测试并生成覆盖率报告（CI 使用）
test-cov:
	source .venv/bin/activate && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=50

# 仅单元测试 + 覆盖率
test-unit:
	source .venv/bin/activate && python -m pytest tests/unit/ -v --tb=short --cov=app --cov-report=term-missing

# 仅集成测试 + 覆盖率
test-integration:
	source .venv/bin/activate && python -m pytest tests/integration/ -v --tb=short --cov=app --cov-report=term-missing

# 生成 HTML 覆盖率报告并在浏览器中打开
test-report: test-cov
	open htmlcov/index.html
