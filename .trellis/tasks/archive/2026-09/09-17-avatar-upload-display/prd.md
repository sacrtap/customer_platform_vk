# PRD：头像上传后未正确显示

> 2026-09-17 用户报告（主会话直接处理，未派发子代理）

## 背景

个人信息页（`frontend/src/views/Profile.vue`）上传头像后提示成功、DB 已更新，但头像区域仍显示默认首字母。

## 需求

上传头像后，个人信息页头像正确显示为新上传的图片。

## 验收标准（AC）

- **AC1**：开发环境下（vite dev server :5173），`GET /uploads/avatars/*.jpg` 返回 `200 image/jpeg`（经前端入口可达）
- **AC2**：浏览器实跑：登录 → 个人信息页 → 上传图片 → 头像区域渲染为新图片（`img.complete && naturalWidth > 0`）
- **AC3**：移除头像后恢复默认首字母，DB `avatar_url` 清空
- **AC4**：生产 nginx 行为不变（已有 `location /uploads/` 转发）
- **AC5**：break-loop 分析沉淀至 `.trellis/spec/guides/cross-layer-thinking-guide.md`

## 已知缺口 / 边界

- 同链路 AppHeader 顶部头像与下拉头像（同一 `avatar_url`）一并修复，不单独列 AC
- 后端其他相对路径（`payment_proof`、`detail_file_path`、减免附件 `file_path`）目前仅走 API blob 下载或文本展示，无 img/href 直链，不在本次范围
