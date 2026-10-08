# Code Review Guide（OCR 在网关不稳定环境下的执行策略）

> 沉淀于 2026-09-30（客户导入导出 + 行业类型审查），供后续 `ocr review` 会话复用。
> 基线问题：bifrost 网关（9router）对大批量请求持续 524/530/502/503，全量审查 2 轮（10 文件/轮）全部失败，单轮耗时 ~16 分钟全耗在重试上。

## 触发场景

- 运行 `ocr review` 时输出 `provider error (HTTP 524/530/502/503)` 或 `all N file review(s) failed`
- LLM 连通性正常（`ocr llm test` 通过）但 review 失败——这是**网关对大请求超时**，不是 LLM 配置问题

## 有效策略（2026-09-30 验证）

1. **不要全量重试**：10 文件全量 plan 请求过大，网关必然超时。先 `--preview` 看分组，再拆小。
2. **分组小批量并行**：按主题拆分，每组 ≤6 文件（可单文件），`--exclude` 反选其他组，并行跑
   多组（各用独立 `--output` 文件防覆盖）。分组后单组成功率显著提升（部分组全成功）。
3. **多轮补审**：失败文件 `--resume <session>` 重试（**必须带 `--from/--to`**——`--resume` 单独用
   报 `workspace resume is not supported`）。失败是文件级的：同组内 routes 成功 services 失败很常见。
4. **判断成功与否看 output 文件**：命令退出码与 summary 可能不一致（summary 显示 failed 但部分
   文件已产出评论，见 `Review partially complete: N finding(s)`）。用 `read` 读完整 output 文件，
   统计 `path + severity + category` 字段，按文件去重。
5. **会话 id 复用**：失败后 `ocr review --from <ref> --to <ref> --resume <session-id> -b "…" --output …`，
   避免重新读 diff（第二次 resume 输入 62K tokens 比首轮快）。

## 报告规范

- 报告存放 `docs/code-review/YYYY-MM-DD-<主题>-review.md`（日期-主题-review）
- 头部固定字段：日期 / 工具版本 / 范围（refs + 文件数 + 增删行）/ LLM / 审查耗时 / 发现问题数
- 测试文件按项目惯例不纳入 LLM 审查（由 pytest 覆盖）；.trellis 为 unsupported_ext
- 按 severity 分组（critical/high/medium/low），low 中明显合理的也修复并记录
- 验证表列出：相关测试集结果、新增回归测试、静态检查（ruff/vue-tsc）、前端单测

## 修复后的连带检查

- 删除路由内手动审计后，**审计断言需按中间件真实命名修正**（本次 `test_update_writes_audit_log`
  因 `module='industry_type'` → `'industry-types'`、`record_type` → 模型类名小写而失败）
- 回归测试优先补「审查发现的高/中危行为」：本次新增 3 个（重名经理行级报错、update 撞软删同名 409、
  空白枚举按未填处理）
