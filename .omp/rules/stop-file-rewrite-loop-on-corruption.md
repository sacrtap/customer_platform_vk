---
name: stop-file-rewrite-loop-on-corruption
description: "当助手文本中出现文件损坏/回滚信号时，立即停止对该文件的进一步修改并提交已完成工作"
condition: "(git checkout HEAD|文件已恢复|回滚|rollback|truncat|损坏).{0,30}(再次|重新|retry|try again|继续|下一次)"
scope: "text"
---

你已经检测到文件损坏并执行了回滚。**立即停止对该文件的进一步自动修改**。

**退出协议**：
1. `git add -A && git commit -m 'chore: save progress before retrying'` — 锁定已完成的组件/测试等独立工作
2. 向用户精确报告：哪个文件损坏、当前行数、已完成什么、还剩什么
3. 明确告诉用户自动修改已停止，等待下一步指令
4. **绝对不要**再次尝试用 bash/Python/sed 修改同一文件 — 这会延续损坏循环

如果用户要求继续，优先选择：派发子代理 或 请求用户手动修改
