# 基于 VitePress 的开放平台开发者文档站

## Goal

将当前 `https://customer-staging.jiazoushi.com/openapi` 路径下由前端 SPA 手写的文档页（`OpenApiGuide.vue`）替换为基于 **VitePress** 的独立开放平台开发者文档站，以 **API 输出为主**（guides / API reference / changelog），认证方式围绕现有「API-Key 管理」功能展开说明。

## 背景与现状（codegraph 已核实）

- 当前 `/openapi` 为前端路由，渲染 `frontend/src/views/OpenApiGuide.vue`（public，无需登录），内容为手写文档：概述、认证、balances 接口、渠道编码对照、错误码。
- 后端开放平台 API 仅一个蓝图 `openapi_bp`（prefix `/api/v1/erp`），目前**唯一端点** `GET /balances`（ERP 渠道客户余额查询）。
- API-Key 认证：`backend/app/middleware/auth.py` 的 `_authenticate_api_key`，要求 `Authorization: Bearer {key}`，错误码 40104（无效/停用）、40105（过期）。
- API-Key 管理已完备：后端 `api_keys_bp`（`/api/v1/api-keys`，权限 `api_keys:manage`）+ 前端「系统管理 → API-Key」页面（创建/启停/删除，`vk_` 前缀，key 仅创建时展示一次明文）。
- 部署：SPA 由 nginx（`deploy/docker/frontend-nginx.conf`）托管，`try_files` fallback，`/api/` 反代 Sanic:8000。

## Requirements

- R1: 盘点后端全部对外 API（`openapi_bp` 及其余可能开放接口），输出端点、方法、参数、响应、认证方式清单，标注数据来源文件
- R2: VitePress 站点落地——独立工程（含构建脚本），产物可部署到 `/openapi` 路径（`base: '/openapi/'`）
- R3: 文档站结构设计：导航（guides / api-reference / changelog 等）、每接口页内容模板（描述、参数表、请求/响应示例、错误码）
- R4: 认证章节围绕「API-Key 管理」展开：Key 如何获取（系统管理 → API-Key 页面）、如何传递（`Authorization: Bearer`）、状态含义（启用/停用/过期/删除）、安全注意事项；提供 curl/Python 等示例代码
- R5: 移除 `/openapi` 路径下当前内容——删除或停用 `OpenApiGuide.vue` 及其路由，`/openapi` 由 VitePress 静态站承载
- R6: 部署方案（nginx `location /openapi/` 指向静态产物，与 SPA 共存；staging/prod 路径一致性）与文档维护流程（随 API 变更如何更新、构建发布）

## Acceptance Criteria

- [ ] AC1: API 现状清单产出（端点、方法、参数、响应、认证），标注数据来源文件
- [ ] AC2: VitePress 独立工程可本地构建，产物以 `base: '/openapi/'` 输出
- [ ] AC3: 文档站结构（目录、导航、页面模板）设计完成，每接口页含描述/参数/请求示例/响应示例/错误码
- [ ] AC4: 认证章节明确指向 API-Key 管理（获取、传递、状态、安全），示例代码可用
- [ ] AC5: `OpenApiGuide.vue` 及 `/openapi` 路由移除，`/openapi` 路径由 VitePress 产物接管（含 nginx 配置方案）
- [ ] AC6: design.md 通过 task.py validate（上下文与验收可复核）

## Notes

- 本任务第一阶段聚焦需求分析与设计（design.md）；文档站搭建与写作由后续实施阶段承接
- 现有入口：`backend/app/routes/openapi.py`（openapi_bp，url_prefix `/api/v1/erp`）；`backend/app/middleware/auth.py`（API-Key 认证）；`backend/app/routes/api_keys.py` + `backend/app/services/api_key_service.py`（Key 管理）
- 技术栈：Sanic 24.12 + sanic-ext + pydantic（无内置 OpenAPI 规范生成）；前端 Vite 7 + Vue 3.4（Node 环境已具备，可承载 VitePress 构建）
