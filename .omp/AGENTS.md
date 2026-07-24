# 客户运营中台开发指南

**最后更新**: 2026-06-30
**CI 要求**: 测试覆盖率 ≥50%

---

## Project Overview

客户运营中台（Customer Operations Platform）是一套面向企业内部使用的客户信息管理与运营系统，实现：

- **账号治理**：RBAC 权限模型 + 自定义角色，细粒度权限控制
- **客户信息管理**：统一客户基础信息 + 画像数据，支持 Excel 导入/导出
- **结算管理**：3 种计费模式（定价/阶梯/包年），余额管理（先赠后实），完整结算流程
- **画像管理**：双等级体系（规模等级 + 消费等级），自定义标签，组合筛选
- **客户分析**：消耗分析、回款分析、健康度分析、画像分析四大维度，预测回款

## 项目硬规则

项目硬规则始终优先：数据库事务、权限校验、测试覆盖率、Python 版本、并发安全、文件修改前读取、中文回复和 pre-commit 环境规则见 `.omp/RULES.md`。

---

@ .omp/rules/architecture.md
@ .omp/rules/directories.md
@ .omp/rules/commands.md
@ .omp/rules/conventions.md
@ .omp/rules/files.md
@ .omp/rules/runtime.md
@ .omp/rules/testing.md
@ .omp/rules/agents.md
@ .omp/rules/refactoring.md

---

## 更多信息

- **完整技术栈、启动指南和项目状态**: [README.md](../README.md)
- **详细开发命令**: `Makefile` (根目录), `backend/Makefile`
- **代码结构探索**: `read backend/app/`, `read frontend/src/`, `codegraph_explore`
- **测试配置**: `backend/pyproject.toml`, `frontend/vite.config.ts`, `frontend/package.json`
- **CI/CD 流程**: `.github/workflows/`
- **全局规则**: `~/.omp/agent/SYSTEM.md`, `~/.omp/agent/AGENTS.md`
- **硬规则**: `.omp/RULES.md`（始终附着）
- **CodeGraph 使用**: 见全局 SYSTEM.md 第 87-94 行
