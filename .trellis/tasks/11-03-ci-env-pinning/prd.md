# CI 环境固定化：pin runner/Python 与 Playwright 容器化

## Goal

`ubuntu-latest` 迁移至 ubuntu26.04 导致 CI 两处失败（Playwright 不支持新镜像、pandas 在 runner 默认 Python 3.14 编译失败）。固定 CI 环境版本，使 runner 镜像变更不再影响测试链路。

## Requirements

- R1 所有 workflow 的 `runs-on` pin 到显式版本，消除浮动标签风险
- R2 `migration-gate` 的 Python 版本显式声明为 3.12（对齐项目硬规则）
- R3 E2E 浏览器依赖不再来自 runner 宿主机安装，改用版本对齐的官方容器镜像

## Acceptance Criteria

- [x] AC1 4 个 workflow 共 20 处 `runs-on: ubuntu-latest` → `ubuntu-24.04`
- [x] AC2 migration-gate 补 `actions/setup-python@v5` + `PYTHON_VERSION`（3.12）
- [x] AC3 pr-checks（smoke）与 e2e-full（全量+视觉回归）测试步骤改为 `docker run mcr.microsoft.com/playwright:v1.59.1-jammy`（版本与 package-lock 1.59.1 精确对齐）
- [x] AC4 `--network host` 使容器内 localhost 直达 PG/Redis services 与 backend/frontend，DATABASE_URL 等零改动
- [x] AC5 CI 实测：E2E Tests 44 passed、Backend Integration 13 passed、Migration Gate 通过、PR Quality Gate passed（run 41573085609）

## Notes

- 部署链路（deploy.yml）用 Docker Buildx + SSH，本身不受影响，一并 pin 保持与历史成功运行一致的环境
- 顺带修复：`npm ci` 加 `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`，host 侧不再下载无人使用的浏览器
- 提交：`d0ae255` fix(pin) + `f5c099a` perf(容器化)
