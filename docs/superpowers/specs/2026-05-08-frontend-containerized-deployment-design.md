# 前端容器化部署设计文档

**日期**: 2026-05-08
**状态**: 已确认
**作者**: AI Assistant

---

## 问题描述

Staging 环境部署后，访问 `http://localhost:8000` 返回后端 API JSON 响应而非前端页面。

**根因**：当前部署流程只部署了后端 Docker 容器，没有部署前端构建产物。

## 解决方案

采用**容器化前后端分离部署**方案：
- 前端构建产物嵌入独立的 Nginx Docker 镜像
- Nginx 作为统一入口（端口 80），同时提供静态文件和 API 反向代理
- 后端服务仅在内网暴露（端口 8000），不直接对外

## 架构设计

```
┌──────────────────────────────────────────────────────┐
│                   Staging Server                     │
│                                                      │
│  Docker Compose                                      │
│  ┌────────────────────┐    ┌──────────────────────┐  │
│  │  nginx-frontend    │    │  Backend Services    │  │
│  │  (port 80 → 80)    │    │                      │  │
│  │                    │    │  ┌─────┐ ┌─────┐    │  │
│  │  / → 静态文件      │    │  │ App │ │ DB  │    │  │
│  │  /api/* → app:8000 │─── │  │:8000│ │:5432│    │  │
│  └────────────────────┘    │  └─────┘ └─────┘    │  │
│                            └──────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 路由规则

| 路径                         | 处理方式                           |
| ---------------------------- | ---------------------------------- |
| `/`                          | Nginx 返回前端 `index.html`          |
| `/dashboard` 等 SPA 路由     | Nginx 返回 `index.html`（SPA 回退）  |
| `/api/*`                     | 反向代理到 `app:8000/api/*`          |
| `/health`                    | 反向代理到 `app:8000/health`         |
| 静态资源 (js/css/图片等)      | Nginx 直接提供，设置长期缓存         |

## 文件变更清单

| 文件                                  | 操作   | 说明                           |
| ------------------------------------- | ------ | ------------------------------ |
| `deploy/docker/frontend-nginx.conf`   | 新增   | Nginx 配置（SPA + API 代理）   |
| `deploy/docker/frontend.Containerfile`| 新增   | 前端 Nginx 镜像构建文件        |
| `.github/workflows/deploy.yml`        | 修改   | 构建并推送前端镜像             |
| `deploy/docker-compose.yml`           | 修改   | 添加 nginx 服务，调整端口映射  |
| `deploy/scripts/deploy.sh`            | 修改   | 支持前端镜像部署               |

## 部署流程

### CI 阶段
1. 构建后端镜像并推送到 GHCR
2. 构建前端镜像并推送到 GHCR

### 部署阶段
1. SSH 连接到 staging 服务器
2. 拉取后端和前端镜像
3. 重新打标签为 `customer_platform_app:latest` 和 `customer_platform_frontend:latest`
4. 运行 `deploy.sh --use-remote-image` 启动服务

### 访问方式
- 前端页面：`http://服务器IP/` 或 `https://staging.jiazoushi.com/`
- API 接口：`http://服务器IP/api/*`
- 健康检查：`http://服务器IP/health`

## 安全考虑

- 后端端口 8000 不再对外暴露，只能通过 Nginx 反向代理访问
- Nginx 配置中添加必要的 CORS 和代理头
- 静态资源设置长期缓存减少带宽

## 回滚方案

如果部署后出现问题，可以通过以下方式回滚：
1. SSH 到服务器
2. 运行 `docker compose -f deploy/docker-compose.yml down`
3. 重新拉取旧版本镜像
4. 运行 `docker compose -f deploy/docker-compose.yml up -d`
