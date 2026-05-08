# 客户运营中台 - 前端 Nginx 容器镜像
# 多阶段构建：Node.js 构建 + Nginx 生产

# 阶段 1: 构建前端
FROM node:22-alpine AS builder

WORKDIR /build

# 复制依赖文件并安装
COPY frontend/package*.json ./
RUN npm ci

# 复制源代码并构建
COPY frontend/ ./
RUN npm run build

# 阶段 2: 生产镜像
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY deploy/docker/frontend-nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8082

CMD ["nginx", "-g", "daemon off;"]
