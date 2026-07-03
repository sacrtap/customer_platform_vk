---
name: delete-model-check-references
description: "删除模型或数据库表前，必须先全局搜索所有引用点并一次性清理"
condition: "(删除|移除|drop).*(模型|表|table|model)"
scope: "tool:write(*.py)"
---

在删除模型或数据库表之前，必须先使用 grep 或 ast_grep 全局搜索所有引用点（包括服务层、路由层、测试文件、前端组件等），列出完整的清理清单后再执行删除操作。避免分多次修改导致遗漏或测试失败。