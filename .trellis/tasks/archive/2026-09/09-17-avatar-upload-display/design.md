# 设计：头像上传后未正确显示

## 根因分析

### 数据流

```
后端 upload_avatar (routes/users.py:692)
  → 保存到 <file_storage_path>/avatars/{user_id}_{uuid}.jpg
  → 返回 { "avatar_url": "/uploads/avatars/{user_id}_{uuid}.jpg" }
  → users.avatar_url 入库
前端 Profile.vue handleAvatarUpload (L264-311)
  → formData.avatar_url = res.data.avatar_url   # 拦截器返回 response.data，取值正确
  → <img :src="formData.avatar_url">            # 浏览器请求 /uploads/...
```

### 根因定位（Bayesian 更新）

| 假设 | 先验 | 证据 | 后验 |
|---|---|---|---|
| H1 vite 代理缺 /uploads | 60% | curl 5173 → `200 text/html`；curl 8000 → `200 image/jpeg`（Content-Type 区分性证据） | **~100%** |
| H2 响应拦截器解包导致 avatar_url undefined | 25% | 源码核对：拦截器返回 `response.data`（`{code,data,message}`），`res.data.avatar_url` 有值 | ~0% |
| H3 后端未挂载静态服务 | 15% | `main.py:121 app.static("/uploads/", ...)`；8000 直连返回 image/jpeg | ~0% |

**结论**：H1 —— 后端契约「avatar_url 为相对路径」隐含「消费端入口必须转发 /uploads」前提，该前提只在生产 nginx 满足（`deploy/docker/frontend-nginx.conf` 有 `location /uploads/`），开发 vite proxy 只配了 `/api`。SPA fallback 对未知路径返回 200 text/html，掩盖了问题（只看状态码会误判正常）。

## 修复方案

**最小改动**：`frontend/vite.config.ts` 的 `server.proxy` 增加：

```ts
'/uploads': {
  target: 'http://localhost:8000',
  changeOrigin: true,
},
```

与生产 nginx `location /uploads/` 同构，vite 检测配置变更自动重启后生效。

**不改**：后端、前端组件逻辑、nginx 配置（均已正确）。

## 验证手法（沉淀）

```bash
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:5173/uploads/avatars/x.jpg
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8000/uploads/avatars/x.jpg
```

断言两侧 Content-Type 一致（image/jpeg），而非仅看 HTTP 200。
