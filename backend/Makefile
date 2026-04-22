.PHONY: test test-fast test-cov test-parallel test-unit test-integration test-changed test-report

# 默认：运行所有测试（无覆盖率，快速反馈）
test:
	source .venv/bin/activate && python -m pytest tests/

# 最快：仅运行单元测试（不启动数据库）
test-fast:
	source .venv/bin/activate && python -m pytest tests/unit/ -v --tb=short

# 并行：使用多进程加速（需要 pytest-xdist）
test-parallel:
	source .venv/bin/activate && python -m pytest tests/ -n auto --tb=short

# 覆盖率：运行测试并生成覆盖率报告（CI 使用）
test-cov:
	source .venv/bin/activate && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=50

# 仅单元测试 + 覆盖率
test-unit:
	source .venv/bin/activate && python -m pytest tests/unit/ -v --tb=short --cov=app --cov-report=term-missing

# 仅集成测试 + 覆盖率
test-integration:
	source .venv/bin/activate && python -m pytest tests/integration/ -v --tb=short --cov=app --cov-report=term-missing

# 运行自上次提交以来更改的测试（需要 pytest-testmon）
test-changed:
	source .venv/bin/activate && python -m pytest tests/ --testmon

# 生成 HTML 覆盖率报告并在浏览器中打开
test-report: test-cov
	open htmlcov/index.html
