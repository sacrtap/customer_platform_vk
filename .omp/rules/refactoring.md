## 重构流程规范

### 重构前验证
- 跨文件或多步骤重构必须先使用 `writing-plans` 产出执行规格；规格必须列明目标文件、切分顺序、回滚方式和验证命令
- 若重构源于 bug 或测试失败，必须先使用 `systematic-debugging` 证明根因，再开始结构调整
- 制定重构计划，包含：影响范围分析、分步实施计划、回滚方案、测试策略

### 重构中验证
- 每步都要运行测试
- 发现 regression 立即停止并修复

### 重构后验证
- 验证行为兼容性
- 更新相关文档（directories.md, files.md, architecture.md）
- 声明重构完成前必须使用 `verification-before-completion`，并记录至少一条覆盖重构影响面的验证证据
- 确认所有 import 路径已更新
- [ ] 现有测试全部通过
- [ ] 重构计划已制定
- [ ] 每步都运行测试
- [ ] 行为兼容性已验证
- [ ] 文档已更新
- [ ] import 路径已更新

## 大型组件文件重构（Vue/React 2000+ 行）

### 问题
直接修改大型文件容易陷入：文件损坏 → 回滚 → 再损坏的死循环。

### 推荐模式
1. **拆分前先 commit**：确保起始状态是干净的 commit
2. **subagent + Python 行切片**：subagent 的任务 prompt 要提供具体的 Python 脚本（使用 `lines[:N] + [新组件引用] + lines[N+M:]` 行切片，整体读写一次完成）
3. **每组件独立 commit**：出问题时 revert 单个 commit 即可
4. **修改前备份**：`cp <file> /tmp/<file>.backup`，损坏时 `git checkout HEAD -- <file>` 回滚

### 目标行数
| 文件 | 原始行数 | 拆分后目标 |
|------+----------|------------|
| 页面级 .vue（多 tab） | 2000+ | ≤800（保留容器+table+导入） |
| 对话框内联 | 100-200 | 抽为独立组件 |
| 选项卡（a-tab-pane） | 50-150 | 抽为独立组件 |

### 示例：Detail.vue 拆分结构
```
Detail.vue (父组件)
├── <a-tabs> 容器
│   ├── CustomerBasicTab.vue     → 基础信息
│   ├── CustomerProfileTab.vue   → 画像信息
│   ├── CustomerBalanceTab.vue   → 余额信息
│   ├── CustomerInvoicesTab.vue  → 结算单
│   └── CustomerUsageTab.vue     → 用量数据
├── EditCustomerDialog.vue       → 编辑客户
└── TagSelectorDialog.vue        → 标签选择器
```

## 文件修改安全规则

### Python 脚本修改
- 修改前先 `cp <file> /tmp/<file>.backup`
- 不要使用 `re.sub` 做内容替换（容易意外截断文件）
- 仅使用行切片（`lines[:N]` + body + `lines[N:]`）做结构替换
- 写完后立即 `wc -l` 验证行数，确认与预期相符

### edit 工具规则
- 每次 read 后重新获取 tag，不用缓存 tag（tag 在每次 read 后刷新）
- 大范围替换（>20 行）使用 `SWAP.BLK` 而非 `SWAP`，避免行号偏移
- 修改后立即 `read` 验证实际内容

### 工具选择策略
| 场景 | 推荐工具 |
|------|----------|
| 插入/删除几行 | `edit` 工具 |
| 替换 >20 行块 | `edit` 工具 `SWAP.BLK` |
| 大规模文件重构 | subagent + Python 行切片 + 整体 write |
| 紧急回滚 | `git checkout HEAD -- <file>` |

### 损坏恢复
```bash
# 恢复到最后 commit 状态
git checkout HEAD -- <file>

# 验证恢复
wc -l <file>
npx vue-tsc --noEmit
```
