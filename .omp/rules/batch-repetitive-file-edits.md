---
name: batch-repetitive-file-edits
description: "Prefer batch tools (ast_edit, bash, codemods) over sequential manual edits when fixing the same pattern across multiple files"
condition: "批量修复.*文件|遍历.*页面|所有.*页面.*添加|修复.*\\d+.*个页面"
scope: "text"
---

⚠️ 本次会话中因逐文件手动 edit 导致 3+ 次重复往返、CSS 修复遗漏和提交遗漏。

✅ 正确做法：
- Vue/TS 语法模式修复 → 用 `ast_edit` 一次性覆盖所有目标文件
- CSS/HTML 批量替换 → 用 `bash` + Python 脚本一次性处理
- 修复前用 `grep -c` 或 `glob` 确认完整文件列表
- 提交前用 `git diff --stat` + `git status --short` 做最终检查

❌ 禁止：
- 对多个相同结构的文件逐一执行 `edit` + 多次 `read`
- 逐步修改同一 CSS 块（先删再改再补）导致错误和往返
- 未完整检查所有改动就直接 commit