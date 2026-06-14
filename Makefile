.PHONY: help install dev test lint format pre-commit deploy-build deploy-staging deploy-production

help: ## 显示帮助信息
	@echo "可用命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖（首次使用）
	@echo "=== 安装后端依赖 ==="
	cd backend && python -m pip install -r requirements.txt
	@echo "=== 安装前端依赖 ==="
	cd frontend && npm install
	@echo "=== 安装 pre-commit hooks ==="
	pre-commit install

dev: ## 启动开发环境
	@echo "=== 启动后端 ==="
	cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "=== 启动前端 ==="
	cd frontend && npm run dev

test: ## 运行测试
	@echo "=== 后端单元测试 ==="
	cd backend && python -m pytest tests/unit/ -x --tb=short -q
	@echo "=== 后端集成测试 ==="
	cd backend && python -m pytest tests/integration/ -x --tb=short -q
	@echo "=== 前端类型检查 ==="
	cd frontend && npx vue-tsc --noEmit
	@echo "=== 前端单元测试 ==="
	cd frontend && npm run test:unit

lint: ## 代码检查
	@echo "=== 后端代码检查 ==="
	cd backend && ruff check app/ tests/
	cd backend && ruff format --check app/ tests/
	@echo "=== 前端代码检查 ==="
	cd frontend && npm run lint

format: ## 代码格式化
	@echo "=== 后端代码格式化 ==="
	cd backend && ruff check --fix app/ tests/
	cd backend && ruff format app/ tests/
	@echo "=== 前端代码格式化 ==="
	cd frontend && npm run lint:fix

pre-commit: ## 运行 pre-commit 检查
	pre-commit run --all-files

check: lint test ## 完整检查（lint + test）
	@echo "✅ 所有检查通过"

deploy-build: ## 构建部署镜像（本地测试）
	@echo "=== 构建后端镜像 ==="
	docker build -t customer_platform_app:latest -f deploy/docker/Containerfile backend/
	@echo "=== 构建前端镜像 ==="
	docker build -t customer_platform_frontend:latest -f deploy/docker/frontend.Containerfile .

deploy-staging: ## 部署到 Staging 环境
	@echo "=== 部署到 Staging ==="
	@echo "请确保已配置 .env.staging 文件"
	bash deploy/scripts/deploy.sh staging

deploy-production: ## 部署到 Production 环境
	@echo "=== 部署到 Production ==="
	@echo "请确保已配置 .env.production 文件"
	bash deploy/scripts/deploy.sh production

clean: ## 清理临时文件
	@echo "=== 清理 Python 缓存 ==="
	find backend -type d -name __pycache__ -exec rm -rf {} +
	find backend -type f -name "*.pyc" -delete
	@echo "=== 清理前端构建 ==="
	cd frontend && npm run clean || true
	@echo "=== 清理日志文件 ==="
	find . -type f -name "*.log" -delete

db-migrate: ## 运行数据库迁移
	cd backend && python -m alembic upgrade head

db-rollback: ## 回滚数据库迁移
	cd backend && python -m alembic downgrade -1

db-reset: ## 重置数据库（危险！）
	@echo "⚠️  警告：这将删除所有数据！"
	@read -p "确认继续？(y/N) " confirm && [ $$confirm = "y" ] || exit 1
	cd backend && python -m alembic downgrade base
	cd backend && python -m alembic upgrade head
	cd backend && python scripts/seed.py
