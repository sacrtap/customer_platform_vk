# frontend/src 上下文

> 本文件是 `frontend/src` 的包级上下文，**仅补充根级指令未覆盖的目录导航与规范入口**。
> 全局规则（硬规则 / 中文回复 / 文件修改前读取 / 测试覆盖率）见根级 `AGENTS.md` 与 `.omp/RULES.md`，此处不重复。
> 规范正文一律以 `.trellis/spec/frontend/` 为准（总入口 `index.md`），本文件只做路由，不复述正文。

## 分层边界

目录细节见 `.trellis/spec/frontend/directory-structure.md`。

| 位置 | 职责 | 落点规则 |
|---|---|---|
| `views/<module>/` | 页面；页面私有组件放同级 `components/`，详情页 tab 放 `detail/` | 只被一个模块使用的组件不进 `components/` |
| `components/` | 跨模块共享组件 | `ui/` 放无业务原语；`charts/`、`invoice/`、`vr/`、`layout/` 按域分组 |
| `composables/` | 页面逻辑抽取（`use<Domain>.ts`） | 页面状态与动作优先抽 composable，不堆在 SFC |
| `stores/` | Pinia store（setup 风格） | 仅全局 / 跨页面状态；页面态留在 composable |
| `api/<module>.ts` | 类型化请求函数 + 同域类型 | 禁止组件内直接 axios |
| `types/`、`utils/`、`constants/` | 共享类型 / 纯函数 / 常量 | 保持无业务副作用 |

## 变更前必读路由

| 改动 | 入口 |
|---|---|
| 新增 / 修改 `.vue` | `.trellis/spec/frontend/component-guidelines.md`：**Modal 表单模式**、**导入弹窗契约**、**状态机时间线**（共享状态推导单一 owner）、**上传区样式链**（受控 file-list 与上传错误处理契约 + a-upload 内部样式/DOM 陷阱 + 共享组件外观归属） |
| 新增 / 修改类型 | `.trellis/spec/frontend/type-safety.md`（类型组织、nullable、泛型、禁止 `any`） |
| 页面 / 全局状态 | `.trellis/spec/frontend/state-management.md`（Pinia、server state、缓存、持久化） |
| 抽取页面逻辑 | `.trellis/spec/frontend/hook-guidelines.md`（页面级 composable 模板、拆分 god composable） |
| 用 `edit` 改 `.vue` | `.omp/rules/edit-vue-full-path.md`（仓库相对全路径 + 当次 `read` 的哈希标签） |

补充：上传区 / 共享组件反复出现样式返工时，先核对 `component-guidelines.md` 的「共享组件外观归属」与「受控 file-list 与上传错误处理契约」两节；缺陷修复后的经验回写规范走 `.agents/skills/trellis-update-spec/`。

## 本地验证命令

```bash
cd frontend
npx vitest run              # 全量单元测试
npx vue-tsc --noEmit        # 类型检查（等价 pnpm type-check）
npx eslint src/ && npx prettier --check src/
```

前端改动完成前至少跑 `vitest run` 与 `vue-tsc --noEmit`；只改样式也要跑相关组件测试。
