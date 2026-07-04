---
name: edit-vue-full-path
description: "edit 工具必须使用完整仓库相对路径，不能使用裸文件名或过期哈希"
condition: "\\[[A-Z]\\w*\\.vue#"
scope: "tool:edit"
---

edit 工具的路径必须是完整的仓库相对路径（如 `frontend/src/views/customers/Index.vue#TAG`），不能是裸文件名（如 `[Index.vue#TAG]`）。路径中的 `#TAG` 必须是当前会话中通过 `read` 获取的最新哈希标签，不能从历史记录或上下文中复用过期的哈希。每次 edit 前先 `read` 目标文件，复制文件头返回的 `[path#TAG]` 完整格式。裸文件名会导致 'File not found' 错误，过期哈希会导致编辑被拒绝。