# 执行记录：头像上传后未正确显示

> 对应 `prd.md`（AC1–AC5）与 `design.md`。主会话直接执行，无子代理。

---

## 阶段 1：复现与根因确认（完成）

- [x] 源码核对：前端 `handleAvatarUpload` 取值链正确（拦截器返回 `response.data`，`res.data.avatar_url` 有值）——排除 H2
- [x] 后端静态服务确认：`main.py:121` `app.static("/uploads/", ...)`；认证中间件放行 `/uploads/`——排除 H3
- [x] **复现**（curl 双端对比，关键证据）：

```
前端 5173: HTTP 200, content-type: text/html   ← SPA fallback 吞掉，破图
后端 8000: HTTP 200, content-type: image/jpeg  ← 正常
```

- [x] 生产对照：`deploy/docker/frontend-nginx.conf` 已有 `location /uploads/` → 生产正常、开发必现（同代码双入口行为不一致）

## 阶段 2：修复（完成）

- [x] `frontend/vite.config.ts` proxy 增加 `'/uploads'` 转发（与 nginx 同构）

## 阶段 3：验证（完成）

- [x] AC1：修复后 curl 5173 → `200 image/jpeg`（两个文件样本均通过）
- [x] AC2：浏览器实跑（headless，admin/admin123）：上传 64×64 测试 PNG → 头像区域 `img.complete && naturalWidth=64`，URL 为 `http://localhost:5173/uploads/avatars/18_582737b5.png`
- [x] AC3：点击「移除」→ 恢复默认首字母，后端 profile `avatar_url=""`
- [x] AC4：nginx 配置未改动
- [x] 测试产物清理：删除测试上传文件 `backend/uploads/avatars/18_582737b5.png` 与 /tmp 测试图

## 阶段 4：break-loop 沉淀（完成）

- [x] `.trellis/spec/guides/cross-layer-thinking-guide.md` 新增「Backend Relative Resource URLs Must Be Reachable From Every Frontend Entry」章节（检查清单 + Content-Type 验证手法 + 案例）
- [x] `src/templates/markdown/spec/` 同步：**跳过**（该平台级模板目录在本仓库不存在，`find` 确认）

## 提交

- `39877c8` `fix(frontend): vite 代理补充 /uploads 转发，修复开发环境头像不显示`（含 spec 更新）

## 验收映射表

| AC | 验证手段 | 结果 |
|---|---|---|
| AC1 dev 入口 /uploads 可达 | curl Content-Type 对比（5173 vs 8000） | ✅ 两侧 image/jpeg |
| AC2 上传后头像渲染 | 浏览器实跑（uploadFile → img naturalWidth=64） | ✅ |
| AC3 移除恢复默认态 | 浏览器点击移除 → 前端回退 + DB 清空 | ✅ |
| AC4 生产行为不变 | nginx 配置未改动 | ✅ |
| AC5 分析沉淀 | cross-layer-thinking-guide 新章节 | ✅ |

## 残留风险

- `FILE_STORAGE_PATH` 相对路径随 cwd 漂移问题已存在于 `spec/backend/file-storage.md`（既有登记），本次未触及
- 头像历史文件（如 `18_034e79f8.jpg`）磁盘残留：上传新头像时才删旧文件，属既有设计，非本次范围
